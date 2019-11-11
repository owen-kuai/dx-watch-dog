import requests
import logging
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter

DEFAULT_HEADERS = {
    'User-Agent': "DxWatchDog",
    'Accept-Encoding': ', '.join(('gzip', 'deflate')),
    'Accept': '*/*',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json',
}
LOG = logging.getLogger(__name__)


class ClientError(ConnectionError):
    pass


class HttpClient(requests.Session):
    def __init__(self, base_url, headers: dict = None):
        super(HttpClient, self).__init__()
        self.base_url = base_url
        self.verify = False
        if not headers:
            headers = {}
        self.headers.update(DEFAULT_HEADERS)
        self.headers.update(headers)
        self.mount("http://", HTTPAdapter(max_retries=3))
        self.mount("https://", HTTPAdapter(max_retries=3))

    def url(self, path):
        return urljoin(self.base_url, path)

    @classmethod
    def result_or_raise(cls, response, json=True):
        status_code = response.status_code

        if status_code // 100 != 2:
            msg = "[Status Code {}]: {}".format(status_code, response.text)
            LOG.warning(msg)
            raise ClientError(msg)
        if json:
            return response.json()
        return response.text
