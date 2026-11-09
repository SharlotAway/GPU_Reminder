import json
import logging
import urllib.request


logger = logging.getLogger("GPU-Monitor.PushPlus")


class PushPlus:

    API_URL = "https://www.pushplus.plus/send"

    def __init__(self, token):

        self.token = token

    def send(self, title, content):

        payload = {
            "token": self.token,
            "title": title,
            "content": content,
            "channel": "wechat",
            "template": "html"
        }

        data = json.dumps(
            payload,
            ensure_ascii=False
        ).encode("utf-8")

        request = urllib.request.Request(
            self.API_URL,
            data=data,
            headers={
                "Content-Type": "application/json"
            },
            method="POST"
        )

        logger.info(
            "PushPlus 请求 %s",
            json.dumps({"title": title, "content": content}, ensure_ascii=False),
        )
        try:
            result = self._request(request)
        except Exception as exc:
            logger.warning("PushPlus 请求失败，%s", type(exc).__name__)
            raise
        logger.info("PushPlus 已受理，流水号 %s", result.get("data"))
        return result

    def _request(self, request):
        with urllib.request.urlopen(
            request,
            timeout=15
        ) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

        code = str(result.get("code"))
        if code != "200":
            raise RuntimeError(
                f"PushPlus 返回错误码 {code if code.isascii() and code.isdigit() else 'unknown'}"
            )

        return result
