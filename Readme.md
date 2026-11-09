# GPU Reminder 容器内使用说明

简体中文 · [English](Readme.en.md)

在已部署好的 Docker 容器里进入项目目录：

```bash
cd /path/to/GPU_Reminder
```

## 常用命令

| 命令 | 用途 |
| --- | --- |
| `./start.sh` | 启动后台监控。Docker 容器重启后，执行这条命令恢复监控。 |
| `./status.sh` | 查看监控是否运行及最近日志。 |
| `tail -F logs/latest/monitor.log` | 实时查看最新一轮日志。按 `Ctrl+C` 退出日志查看。 |
| `./stop.sh` | 停止后台监控。 |

监控启动后可以断开 SSH。训练照常从你自己的终端启动。

每次新启动时会创建一个 `logs/年月日-时分秒-后缀/monitor.log`。`logs/latest` 指向最近一次成功启动的目录。监控正在运行时再次执行 `bash start.sh`，会显示当前状态并继续使用本轮日志。

## 环境配置

先进入项目目录，在容器内运行 `nvidia-smi`，确认能看到要监控的 GPU。使用已安装 `pynvml` 的 Python 环境。项目已用 Python 3.11 和 `requirements.txt` 中的依赖版本验证。

如果需要新建一个监控专用环境，在项目目录执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -c 'import pynvml; print("pynvml OK")'
```

在项目根目录创建或编辑 `.env`。把示例里的占位符换成你自己的 PushPlus Token，并确保已在 PushPlus 绑定微信。已部署的容器可以继续使用现有的 `.env`。

```bash
PUSHPLUS_TOKEN='替换为你自己的 PushPlus Token'
# 如果使用上面的 .venv，取消下一行注释
# PYTHON_BIN=.venv/bin/python
GPU_IDS=all
MAX_GPU_UTIL=5
MAX_USED_MEMORY=1500
IDLE_DURATION=60
CHECK_INTERVAL=5
NOTIFY_RETRY_INTERVAL=60
```

| 配置 | 含义 |
| --- | --- |
| `PUSHPLUS_TOKEN` | 必填，用于提交微信推送请求。 |
| `PYTHON_BIN` | 可选，指定监控的 Python 解释器。未填写时，启动脚本先尝试容器预置环境，再从 `PATH` 查找 `python`。 |
| `GPU_IDS` | `all` 监控所有可见 GPU，也可以填写 `0` 或 `0,1`。 |
| `MAX_GPU_UTIL` | 空闲提醒允许的最高整卡利用率，单位为百分比。 |
| `MAX_USED_MEMORY` | 空闲提醒允许的最高整卡已用显存，单位为 MiB。 |
| `IDLE_DURATION` | 空闲条件需要连续满足的时间，单位为秒。 |
| `CHECK_INTERVAL` | 两次检查之间的等待时间，单位为秒。 |
| `NOTIFY_RETRY_INTERVAL` | 推送请求失败后再次尝试前的等待时间，单位为秒。 |

保存后用 `chmod 600 .env` 限制文件权限。将 `.env` 留在容器里，提交 GitHub 时排除它。配置修改后，若监控正在运行，依次执行 `bash stop.sh` 和 `bash start.sh` 让新配置生效。

## 配置 PushPlus 微信推送

1. 打开 [PushPlus 官网](https://www.pushplus.plus/)，用微信扫码登录，并关注「pushplus 推送加」服务号。若个人中心提示需实名认证，先按页面指引完成认证。
2. 在「个人中心 → 个人资料」复制用户 Token，也可使用为这个脚本单独创建的消息 Token。把它填入项目根目录的 `.env` 中的 `PUSHPLUS_TOKEN`。 [Token 说明](https://pushplus.plus/doc/help/token.html)
3. 在官网「发送消息 → 一对一消息」的「试一试」发送测试消息。到微信服务号里确认收到。遇到未送达时，可在 PushPlus 用消息流水号查询最终结果。 [一对一消息说明](https://www.pushplus.plus/doc/function/one.html)

## 微信提醒

- **GPU 空闲**。某张卡的整卡利用率不超过 5%、已用显存不超过 1500 MiB，并持续达标 60 秒时提醒一次。
- **GPU 从空闲变为占用**。某张卡先达到上述空闲条件，之后首次检测到利用率或已用显存超出阈值，就提醒一次。持续占用期间只提醒一次。
- **本容器 GPU 进程退出**。监控确认之前观察到的本容器 GPU 进程退出后提醒。同一个进程使用两张卡也只发一次。退出后 GPU 仍可能被其他任务占用。

每次推送都会记录标题、内容以及 PushPlus 受理或失败情况。进程退出提醒需要监控在进程运行时至少采样到一次。训练是否成功，请查看训练自己的日志。
