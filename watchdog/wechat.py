from watchdog import config
from watchdog.utils import HttpClient


class WeChatSender(object):

    def __init__(self):
        self.base_url = config.WECHART_BASE_URL
        self.key = config.WECHART_KEY
        self.client = HttpClient(self.base_url)

    def send_md(self, md):
        data = {
            "msgtype": "markdown",
            "markdown": {"content": md}
        }
        params = {"key": self.key}
        self.client.post(self.client.url("/cgi-bin/webhook/send"), params=params, json=data)

