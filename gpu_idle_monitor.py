import time
import signal
import logging
from html import escape
from pathlib import Path

from datetime import datetime

import pynvml

from config import load_config
from pushplus import PushPlus


# ==========================================
# Logging
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("GPU-Monitor")


# ==========================================
# Shutdown control
# ==========================================

running = True


def shutdown_handler(signum, frame):

    global running

    logger.info("Received shutdown signal")

    running = False


signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)


# ==========================================
# GPU initialization
# ==========================================

def initialize_gpus(gpu_config):

    gpu_count = pynvml.nvmlDeviceGetCount()

    if gpu_config.strip().lower() == "all":

        gpu_ids = list(range(gpu_count))

    else:

        gpu_ids = [
            int(x.strip())
            for x in gpu_config.split(",")
            if x.strip()
        ]

    if not gpu_ids:

        raise ValueError("没有配置需要监控的 GPU")

    for gpu_id in gpu_ids:

        if gpu_id < 0 or gpu_id >= gpu_count:

            raise ValueError(
                f"GPU {gpu_id} 不存在，当前可见 GPU 数量为 {gpu_count}"
            )

    return gpu_ids


# ==========================================
# GPU information
# ==========================================

def get_gpu_info(gpu_id):

    handle = pynvml.nvmlDeviceGetHandleByIndex(
        gpu_id
    )

    name = pynvml.nvmlDeviceGetName(handle)

    if isinstance(name, bytes):

        name = name.decode()

    memory = pynvml.nvmlDeviceGetMemoryInfo(
        handle
    )

    utilization = pynvml.nvmlDeviceGetUtilizationRates(
        handle
    )

    used_mb = memory.used / 1024**2

    free_mb = memory.free / 1024**2

    gpu_util = utilization.gpu

    return {
        "name": name,
        "used_mb": used_mb,
        "free_mb": free_mb,
        "gpu_util": gpu_util
    }


# ==========================================
# Notification
# ==========================================

def notify_gpu_idle(
    pushplus,
    gpu_id,
    gpu_info,
    idle_duration
):

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    title = f"🎉 GPU {gpu_id} 空闲提醒"

    content = f"""
    <h2>🎉 GPU 空闲提醒</h2>

    <p><b>GPU ID：</b>{gpu_id}</p>

    <p><b>GPU 型号：</b>{gpu_info["name"]}</p>

    <p><b>GPU 利用率：</b>{gpu_info["gpu_util"]}%</p>

    <p><b>已用显存：</b>{gpu_info["used_mb"]:.0f} MB</p>

    <p><b>可用显存：</b>{gpu_info["free_mb"]:.0f} MB</p>

    <p><b>连续空闲时间：</b>{idle_duration:.0f} 秒</p>

    <p><b>检测时间：</b>{timestamp}</p>

    <hr>

    <p>GPU 已达到空闲条件，可以考虑启动训练任务。</p>
    """

    pushplus.send(
        title,
        content
    )


# ==========================================
# Main monitor
# ==========================================

def notify_gpu_occupied(pushplus, gpu_id, gpu_info, detected_at):
    pushplus.send(
        f"GPU {gpu_id} 已被占用",
        "<p>这张卡此前已达到空闲条件，现在已超出空闲阈值。</p>"
        f"<p>GPU 型号：{escape(gpu_info['name'])}<br>"
        f"利用率：{gpu_info['gpu_util']}%<br>"
        f"已用显存：{gpu_info['used_mb']:.0f} MiB<br>"
        f"可用显存：{gpu_info['free_mb']:.0f} MiB<br>"
        f"检测时间：{detected_at:%Y-%m-%d %H:%M:%S}</p>",
    )


def process_identity(path):
    """Read start time and process name. An exited or zombie PID has no identity."""
    try:
        stat = (path / "stat").read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, ProcessLookupError):
        return None
    name, _, tail = stat.partition("(")[2].rpartition(")")
    fields = tail.split()
    if len(fields) < 20:
        raise OSError("Incomplete process stat")
    if fields[0] in {"Z", "X", "x"}:
        return None
    return fields[19], name


def local_gpu_processes(handle, proc_root):
    device = Path(f"/dev/nvidia{pynvml.nvmlDeviceGetMinorNumber(handle)}")
    for entry in pynvml.nvmlDeviceGetComputeRunningProcesses(handle):
        path = proc_root / str(entry.pid)
        try:
            identity = process_identity(path)
            if identity is None or not (path / "ns/pid").samefile(proc_root / "self/ns/pid"):
                continue
            for fd in (path / "fd").iterdir():
                try:
                    if fd.readlink() == device:
                        break
                except FileNotFoundError:
                    continue
            else:
                continue
            if process_identity(path) == identity:
                yield entry.pid, identity
        except OSError:
            continue


class ProcessExitMonitor:
    def __init__(self, retry_interval, proc_root=Path("/proc")):
        self.proc_root = proc_root
        self.retry_interval = retry_interval
        self.tracked = {}
        self.pending = []
        self.retry_at = 0
        self.failed_queries = set()

    def poll(self, gpu_ids, pushplus):
        for gpu_id in gpu_ids:
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
                for pid, (start, name) in local_gpu_processes(handle, self.proc_root):
                    key = (pid, start)
                    if key not in self.tracked:
                        logger.info("跟踪本容器 GPU 进程 PID %s (%r)", pid, name)
                        self.tracked[key] = (name, set())
                    self.tracked[key][1].add(gpu_id)
                self.failed_queries.discard(gpu_id)
            except pynvml.NVMLError as exc:
                if gpu_id not in self.failed_queries:
                    logger.warning("GPU %s 进程查询失败 (%s)", gpu_id, type(exc).__name__)
                    self.failed_queries.add(gpu_id)

        # Loss of a GPU context is independent of the process lifetime.
        for key, (name, cards) in list(self.tracked.items()):
            pid, start = key
            try:
                current = process_identity(self.proc_root / str(pid))
            except OSError:
                continue
            if current is not None and current[0] == start:
                continue
            indices = ", ".join(map(str, sorted(cards)))
            logger.info("本容器 GPU 进程已退出 PID %s (%r)，GPU %s", pid, name, indices)
            self.pending.append(f"<li>PID {pid} ({escape(name)})，GPU {indices}</li>")
            del self.tracked[key]

        if not self.pending or time.monotonic() < self.retry_at:
            return
        try:
            items = "".join(self.pending)
            pushplus.send(
                "本容器 GPU 进程已退出",
                f"<p>监控已确认以下进程退出：</p><ul>{items}</ul>"
                "<p>整卡是否空闲会按显存与利用率单独判断。</p>",
            )
        except Exception as exc:
            self.retry_at = time.monotonic() + self.retry_interval
            logger.warning("进程退出通知请求失败 (%s)，稍后重试", type(exc).__name__)
        else:
            logger.info("PushPlus 已受理 %s 条进程退出事件", len(self.pending))
            self.pending.clear()
            self.retry_at = 0


def main():

    config = load_config()
    process_monitor = ProcessExitMonitor(config["NOTIFY_RETRY_INTERVAL"])

    pushplus = PushPlus(
        config["PUSHPLUS_TOKEN"]
    )

    pynvml.nvmlInit()

    try:

        gpu_ids = initialize_gpus(
            config["GPU_IDS"]
        )

        idle_start = {
            gpu_id: None
            for gpu_id in gpu_ids
        }

        confirmed_idle = set()
        pending_occupied = {}

        notified = {
            gpu_id: False
            for gpu_id in gpu_ids
        }

        last_notify_attempt = {
            gpu_id: 0
            for gpu_id in gpu_ids
        }

        logger.info(
            f"GPU Monitor started. GPU IDs: {gpu_ids}"
        )

        logger.info(
            f"Idle condition: GPU util <= "
            f"{config['MAX_GPU_UTIL']}%, "
            f"used memory <= "
            f"{config['MAX_USED_MEMORY']} MB"
        )

        while running:

            for gpu_id in gpu_ids:

                if not running:
                    break

                try:

                    gpu_info = get_gpu_info(
                        gpu_id
                    )

                    is_idle = (
                        gpu_info["gpu_util"]
                        <= config["MAX_GPU_UTIL"]

                        and

                        gpu_info["used_mb"]
                        <= config["MAX_USED_MEMORY"]
                    )

                    now = time.monotonic()

                    # --------------------------
                    # GPU is idle
                    # --------------------------

                    if is_idle:

                        if idle_start[gpu_id] is None:

                            idle_start[gpu_id] = now

                            logger.info(
                                f"GPU {gpu_id} entered idle state"
                            )

                        idle_time = (
                            now - idle_start[gpu_id]
                        )

                        if idle_time >= config["IDLE_DURATION"]:
                            confirmed_idle.add(gpu_id)

                        should_notify = (
                            idle_time >= config["IDLE_DURATION"]

                            and not notified[gpu_id]

                            and (
                                now
                                - last_notify_attempt[gpu_id]
                            )
                            >= config["NOTIFY_RETRY_INTERVAL"]
                        )

                        if should_notify:

                            last_notify_attempt[gpu_id] = now

                            try:

                                notify_gpu_idle(
                                    pushplus,
                                    gpu_id,
                                    gpu_info,
                                    idle_time
                                )

                                notified[gpu_id] = True

                                logger.info(
                                    f"GPU {gpu_id}: "
                                    "PushPlus accepted idle notification"
                                )

                            except Exception:

                                logger.exception(
                                    f"GPU {gpu_id}: "
                                    "WeChat notification failed"
                                )

                    # --------------------------
                    # GPU is occupied
                    # --------------------------

                    else:

                        if gpu_id in confirmed_idle:
                            confirmed_idle.remove(gpu_id)
                            pending_occupied[gpu_id] = (gpu_info, datetime.now(), now)
                            logger.info("GPU %s 已从空闲转为占用", gpu_id)

                        idle_start[gpu_id] = None

                        notified[gpu_id] = False

                        last_notify_attempt[gpu_id] = 0

                except Exception:

                    idle_start[gpu_id] = None
                    logger.exception(f"GPU {gpu_id}: monitor error")
                    continue

                event = pending_occupied.get(gpu_id)
                if event is not None and now >= event[2]:
                    snapshot, detected_at, _ = event
                    try:
                        notify_gpu_occupied(pushplus, gpu_id, snapshot, detected_at)
                    except Exception:
                        retry_at = time.monotonic() + config["NOTIFY_RETRY_INTERVAL"]
                        pending_occupied[gpu_id] = (snapshot, detected_at, retry_at)
                        logger.exception("GPU %s 占用提醒请求失败，稍后重试", gpu_id)
                    else:
                        del pending_occupied[gpu_id]

            if running:
                process_monitor.poll(gpu_ids, pushplus)
                time.sleep(config["CHECK_INTERVAL"])

    finally:

        pynvml.nvmlShutdown()

        logger.info(
            "GPU Monitor stopped"
        )


if __name__ == "__main__":

    main()
