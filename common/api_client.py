"""HTTP 客户端封装: 基于 requests.Session 的二次封装

职责:
    1. 统一 base_url / 超时 / 请求头, 消除用例中的重复代码
    2. JWT Token 集中管理, 登录后自动携带 Authorization 头
    3. 全量请求-响应日志 (方法/URL/状态码/耗时), 失败时记录响应体, 定位问题无需加打印
"""
import time

import requests
from loguru import logger


class ApiClient:
    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.token: str | None = None

    # ---------- 鉴权管理 ----------
    def set_token(self, token: str | None) -> None:
        """设置/清除 JWT, 后续请求自动携带"""
        self.token = token
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        else:
            self.session.headers.pop("Authorization", None)

    # ---------- 请求方法 ----------
    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)
        start = time.perf_counter()
        try:
            resp = self.session.request(method, url, **kwargs)
        except requests.RequestException as e:
            logger.error(f"请求异常 {method} {url} -> {type(e).__name__}: {e}")
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(f"{method:<6} {path} -> {resp.status_code} ({elapsed_ms:.0f}ms)")
        if resp.status_code >= 500:
            logger.error(f"服务端异常 {method} {path} -> {resp.status_code}: {resp.text[:500]}")
        return resp

    def get(self, path: str, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs):
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs):
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs):
        return self.request("DELETE", path, **kwargs)

    def close(self) -> None:
        self.session.close()
