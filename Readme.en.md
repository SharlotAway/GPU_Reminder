# GPU Reminder

[简体中文](Readme.md) · English

Open a shell in the Docker container where GPU Reminder is deployed and change to the project directory.

```bash
cd /path/to/GPU_Reminder
```

## Daily commands

| Command | What it does |
| --- | --- |
| `./start.sh` | Start the background monitor. Run it again after the Docker container restarts. |
| `./status.sh` | Check whether the monitor is running and show recent log entries. |
| `tail -F logs/latest/monitor.log` | Follow the latest log. Press `Ctrl+C` to leave the log viewer. |
| `./stop.sh` | Stop the background monitor. |

After starting the monitor, you can disconnect from SSH. Start training from your own terminal as usual.

Each new monitor session writes to `logs/YYYYMMDD-HHMMSS-suffix/monitor.log`. The `logs/latest` link points to the most recent successful startup. Running `bash start.sh` while the monitor is already running shows its status and keeps using the current session log.

## Environment setup

Run `nvidia-smi` inside the container to confirm that it can see the GPUs you want to monitor. Use a Python environment with `pynvml` installed. This project has been verified with Python 3.11 and the dependency version in `requirements.txt`.

To create a separate environment for the monitor, run these commands from the project directory:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -c 'import pynvml; print("pynvml OK")'
```

Create or edit `.env` in the project root. Replace the placeholder with your PushPlus token and make sure your WeChat account is linked to PushPlus. If the container already has a working `.env`, you can keep using it.

```bash
PUSHPLUS_TOKEN='replace with your PushPlus token'
# Uncomment the next line if you use the .venv created above
# PYTHON_BIN=.venv/bin/python
GPU_IDS=all
MAX_GPU_UTIL=5
MAX_USED_MEMORY=1500
IDLE_DURATION=60
CHECK_INTERVAL=5
NOTIFY_RETRY_INTERVAL=60
```

| Setting | Meaning |
| --- | --- |
| `PUSHPLUS_TOKEN` | Required. Authenticates WeChat notification requests. |
| `PYTHON_BIN` | Optional. Selects the monitor's Python interpreter. When unset, the startup script tries the container's preset environment, then looks for `python` on `PATH`. |
| `GPU_IDS` | Use `all` for all visible GPUs, or specify IDs such as `0` or `0,1`. |
| `MAX_GPU_UTIL` | Maximum device-wide GPU utilization for the idle alert, as a percentage. |
| `MAX_USED_MEMORY` | Maximum device-wide GPU memory usage for the idle alert, in MiB. |
| `IDLE_DURATION` | How long the idle conditions must hold, in seconds. |
| `CHECK_INTERVAL` | Wait between checks, in seconds. |
| `NOTIFY_RETRY_INTERVAL` | Wait before retrying a failed notification request, in seconds. |

Run `chmod 600 .env` to restrict access to the file. Keep `.env` inside the container and exclude it from GitHub commits. If the monitor is running when you edit the configuration, run `bash stop.sh` and then `bash start.sh` to apply the changes.

## Set up PushPlus for WeChat

1. Sign in with WeChat on the [PushPlus website](https://www.pushplus.plus/) and follow the official “pushplus 推送加” WeChat service account. If PushPlus requires identity verification, follow the instructions in your account.
2. Copy your user token from the profile section of your account, or create a message token for this monitor. Set it as `PUSHPLUS_TOKEN` in the project's `.env`. [PushPlus token documentation](https://pushplus.plus/doc/help/token.html)
3. Use the one-to-one messaging test page on the PushPlus website and confirm that the test message appears in WeChat. If it does not arrive, look up the final delivery result using the message receipt ID. [PushPlus one-to-one messaging guide](https://www.pushplus.plus/doc/function/one.html)

## WeChat alerts

- **GPU idle.** By default, the monitor sends one alert when a GPU stays at or below 5% utilization and 1500 MiB of used memory for 60 seconds.
- **GPU occupied after being idle.** Once a GPU has met the idle conditions, the monitor sends one alert the next time either threshold is exceeded. The GPU can remain occupied without triggering repeated alerts.
- **GPU process exited in this container.** The monitor sends an alert when it confirms that a previously observed GPU process in this container has exited. A process that used both GPUs triggers one alert. Other workloads may still be using either GPU.

The session log records each notification's title and content, plus whether PushPlus accepted or rejected the request. The monitor must observe a process at least once while it is running to report its exit. Check the training log to find out whether training succeeded.
