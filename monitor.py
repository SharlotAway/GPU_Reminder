import time
import pynvml
from datetime import datetime

# =========================
# Configuration
# =========================

CHECK_INTERVAL = 5

# GPU utilization threshold
MAX_GPU_UTIL = 5

# Maximum used VRAM (MiB)
MAX_USED_MEMORY = 1500

# Required continuous idle duration
IDLE_DURATION = 60

# Select GPUs to monitor
GPU_IDS = None  # None = all GPUs

# =========================
# Initialize
# =========================

pynvml.nvmlInit()

gpu_count = pynvml.nvmlDeviceGetCount()

if GPU_IDS is None:
    GPU_IDS = list(range(gpu_count))

idle_start = {
    gpu_id: None for gpu_id in GPU_IDS
}

notified = {
    gpu_id: False for gpu_id in GPU_IDS
}

print("GPU idle monitor started.")

# =========================
# Monitor
# =========================

try:
    while True:

        for gpu_id in GPU_IDS:

            handle = pynvml.nvmlDeviceGetHandleByIndex(
                gpu_id
            )

            name = pynvml.nvmlDeviceGetName(handle)

            if isinstance(name, bytes):
                name = name.decode()

            memory = pynvml.nvmlDeviceGetMemoryInfo(
                handle
            )

            utilization = (
                pynvml.nvmlDeviceGetUtilizationRates(
                    handle
                )
            )

            used_mb = memory.used / 1024**2
            free_mb = memory.free / 1024**2

            gpu_util = utilization.gpu

            is_idle = (
                gpu_util <= MAX_GPU_UTIL
                and used_mb <= MAX_USED_MEMORY
            )

            now = time.monotonic()

            print(
                f"GPU {gpu_id} | {name} | "
                f"Util: {gpu_util}% | "
                f"VRAM: {used_mb:.0f} MB | "
                f"Free: {free_mb:.0f} MB"
            )

            if is_idle:

                if idle_start[gpu_id] is None:
                    idle_start[gpu_id] = now

                idle_time = now - idle_start[gpu_id]

                if (
                    idle_time >= IDLE_DURATION
                    and not notified[gpu_id]
                ):

                    timestamp = datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                    print("\n" + "=" * 50)
                    print("GPU IS AVAILABLE!")
                    print(f"GPU ID: {gpu_id}")
                    print(f"GPU: {name}")
                    print(f"Free VRAM: {free_mb:.0f} MB")
                    print(f"Time: {timestamp}")
                    print("=" * 50 + "\n")

                    notified[gpu_id] = True

            else:
                idle_start[gpu_id] = None
                notified[gpu_id] = False

        time.sleep(CHECK_INTERVAL)

except KeyboardInterrupt:
    print("Monitor stopped.")

finally:
    pynvml.nvmlShutdown()