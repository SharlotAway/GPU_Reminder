import os


def load_config():

    config = {
        "PUSHPLUS_TOKEN": os.getenv("PUSHPLUS_TOKEN", ""),

        "GPU_IDS": os.getenv("GPU_IDS", "all"),

        "MAX_GPU_UTIL": int(
            os.getenv("MAX_GPU_UTIL", "5")
        ),

        "MAX_USED_MEMORY": float(
            os.getenv("MAX_USED_MEMORY", "1500")
        ),

        "IDLE_DURATION": int(
            os.getenv("IDLE_DURATION", "60")
        ),

        "CHECK_INTERVAL": int(
            os.getenv("CHECK_INTERVAL", "5")
        ),

        "NOTIFY_RETRY_INTERVAL": int(
            os.getenv("NOTIFY_RETRY_INTERVAL", "60")
        ),
    }

    if not config["PUSHPLUS_TOKEN"]:
        raise ValueError(
            "PUSHPLUS_TOKEN 未配置，请检查 .env 文件"
        )

    if config["CHECK_INTERVAL"] <= 0:
        raise ValueError("CHECK_INTERVAL 必须大于 0")

    if config["IDLE_DURATION"] <= 0:
        raise ValueError("IDLE_DURATION 必须大于 0")

    if config["MAX_USED_MEMORY"] < 0:
        raise ValueError("MAX_USED_MEMORY 不能小于 0")

    return config