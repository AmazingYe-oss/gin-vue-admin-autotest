import logging

logger = logging.getLogger(__name__)


class UserApi:
    def __init__(self, session, base_url):
        self.session = session
        self.base_url = base_url

    def login(self, username, password):
        logger.info("调用登录接口 username=%s", username)
        response = self.session.post(f"{self.base_url}/base/login",
                                     json={"username": username, "password": password})
        logger.info("登录返回 HTTP=%s", response.status_code)
        return response