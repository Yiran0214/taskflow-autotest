"""用户/鉴权接口封装层: 用例只关心业务参数, 不接触 HTTP 细节"""
import allure

from common.api_client import ApiClient


class AuthApi:
    def __init__(self, client: ApiClient):
        self.client = client

    @allure.step("注册用户: {username}")
    def register(self, username: str, password: str):
        return self.client.post("/api/v1/auth/register", json={"username": username, "password": password})

    @allure.step("登录用户: {username}")
    def login(self, username: str, password: str):
        return self.client.post("/api/v1/auth/login", json={"username": username, "password": password})

    @allure.step("获取当前用户信息")
    def me(self):
        return self.client.get("/api/v1/users/me")
