"""任务接口鉴权与数据权限测试

覆盖点:
    - 认证: 无 token / 伪造 token / 过期 token 访问任务接口
    - 数据权限: 用户只能访问自己的任务 (越权访问返回 404, 列表/统计相互隔离)
"""
from datetime import datetime, timedelta, timezone

import allure
import jwt
import pytest

from api.auth_api import AuthApi
from common.assertions import assert_status
from utils.data_factory import random_task, unique_username


@allure.feature("任务模块")
@allure.story("接口鉴权")
class TestTaskAuth:

    @allure.title("无 token 访问任务接口统一返回 401")
    @pytest.mark.api
    def test_task_without_token(self, anon_task_api):
        assert_status(anon_task_api.create({"title": "x"}), 401, "创建")
        assert_status(anon_task_api.list(), 401, "列表")
        assert_status(anon_task_api.get(1), 401, "详情")
        assert_status(anon_task_api.delete(1), 401, "删除")

    @allure.title("伪造 token 访问任务接口返回 401")
    @pytest.mark.api
    def test_task_with_invalid_token(self, client):
        client.set_token("not.a.valid.token")
        resp = client.get("/api/v1/tasks")
        client.set_token(None)
        assert_status(resp, 401, "伪造 token 访问")

    @allure.title("过期 token 访问任务接口返回 401")
    @pytest.mark.api
    def test_task_with_expired_token(self, client, settings):
        if not getattr(settings, "secret_key", None):
            pytest.skip("外部服务模式下无法构造过期 token")
        expired = jwt.encode(
            {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
            settings.secret_key, algorithm="HS256",
        )
        client.set_token(expired)
        resp = client.get("/api/v1/tasks")
        client.set_token(None)
        assert_status(resp, 401, "过期 token 访问")
        assert resp.json()["detail"] == "Invalid or expired token"


@allure.feature("任务模块")
@allure.story("数据权限隔离")
class TestDataIsolation:

    @pytest.fixture
    def other_user_client(self, api_client_factory, client):
        """另一个独立用户及其已登录客户端 (独立实例, 与用户A的 token 完全隔离)"""
        info = {"username": unique_username("intruder"), "password": "Pass@12345"}
        resp = AuthApi(client).register(info["username"], info["password"])
        assert_status(resp, 201, "注册其他用户")
        other = api_client_factory()
        login = AuthApi(other).login(info["username"], info["password"])
        assert_status(login, 200, "其他用户登录")
        other.set_token(login.json()["access_token"])
        return other

    @allure.title("越权访问他人任务详情返回 404 (不泄露资源存在性)")
    @pytest.mark.api
    def test_get_others_task(self, task_api, other_user_client, user):
        created = task_api.create(random_task())
        assert_status(created, 201, "用户A创建任务")
        resp = other_user_client.get(f"/api/v1/tasks/{created.json()['id']}")
        assert_status(resp, 404, "用户B访问用户A的任务")

    @allure.title("越权更新/删除他人任务返回 404")
    @pytest.mark.api
    def test_update_others_task(self, task_api, other_user_client):
        created = task_api.create({"title": "用户A的任务"})
        assert_status(created, 201, "用户A创建任务")
        task_id = created.json()["id"]

        resp = other_user_client.patch(f"/api/v1/tasks/{task_id}", json={"title": "篡改"})
        assert_status(resp, 404, "用户B修改用户A的任务")
        assert task_api.get(task_id).json()["title"] == "用户A的任务", "任务被越权修改"

        resp = other_user_client.delete(f"/api/v1/tasks/{task_id}")
        assert_status(resp, 404, "用户B删除用户A的任务")
        assert_status(task_api.get(task_id), 200, "任务仍存在")

    @allure.title("任务列表与统计按用户隔离")
    @pytest.mark.api
    def test_list_isolated(self, task_api, other_user_client):
        assert_status(task_api.create({"title": "用户A的任务"}), 201, "用户A创建任务")
        # 用户B 的列表与统计均为空
        resp = other_user_client.get("/api/v1/tasks")
        assert_status(resp, 200, "用户B查询列表")
        assert resp.json()["total"] == 0, "用户B看到了用户A的任务"
        stats = other_user_client.get("/api/v1/stats/summary")
        assert_status(stats, 200, "用户B查询统计")
        assert stats.json()["total"] == 0
