"""用户/鉴权模块接口测试: 注册、登录、当前用户信息

覆盖点:
    - 注册: 等价类/边界值数据驱动 (用户名长度/字符集, 密码长度)
    - 登录: 正常流、密码错误、用户不存在
    - 鉴权: 无 token / 伪造 token 的异常流
"""
import allure
import pytest

from api.auth_api import AuthApi
from common.assertions import assert_status
from utils.data_factory import unique_username


@pytest.fixture
def auth_api(client):
    return AuthApi(client)


@allure.feature("用户模块")
@allure.story("注册")
class TestRegister:

    @allure.title("数据驱动-用户名/密码边界值注册: {case[name]}")
    @pytest.mark.api
    @pytest.mark.parametrize("case", [
        pytest.param({"name": "3位最短用户名+6位最短密码", "username": "ab1", "password": "123456", "expected_status": 201}, id="username_min_password_min"),
        pytest.param({"name": "20位最长用户名", "username": "a123456789b123456789", "password": "abcdef", "expected_status": 201}, id="username_max"),
    ])
    def test_register_boundary_valid(self, auth_api, case):
        resp = auth_api.register(case["username"], case["password"])
        assert_status(resp, case["expected_status"], "注册边界值")
        data = resp.json()
        assert data["username"] == case["username"]
        assert "id" in data

    @allure.title("数据驱动-非法入参注册: {case[name]}")
    @pytest.mark.parametrize("case", [
        pytest.param({"name": "用户名过短(2位)", "username": "ab", "password": "123456", "expected_status": 422}, id="username_too_short"),
        pytest.param({"name": "用户名过长(21位)", "username": "a123456789b123456789c", "password": "123456", "expected_status": 422}, id="username_too_long"),
        pytest.param({"name": "用户名含非法字符", "username": "bad-user!", "password": "123456", "expected_status": 422}, id="username_invalid_char"),
        pytest.param({"name": "密码过短(5位)", "username": "validuser", "password": "12345", "expected_status": 422}, id="password_too_short"),
        pytest.param({"name": "用户名为空", "username": "", "password": "123456", "expected_status": 422}, id="username_empty"),
    ])
    def test_register_invalid_input(self, auth_api, case):
        resp = auth_api.register(case["username"], case["password"])
        assert_status(resp, 422, f"非法入参注册: {case['name']}")

    @allure.title("注册重复用户名返回 409")
    @pytest.mark.api
    def test_register_duplicate(self, auth_api, user):
        resp = auth_api.register(user["username"], user["password"])
        assert_status(resp, 409, "重复注册")
        assert "exists" in resp.json()["detail"]


@allure.feature("用户模块")
@allure.story("登录")
class TestLogin:

    @allure.title("登录成功返回 JWT 且可访问受保护接口")
    @pytest.mark.api
    def test_login_success(self, auth_api, user):
        resp = auth_api.login(user["username"], user["password"])
        assert_status(resp, 200, "登录")
        data = resp.json()
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 20

        # token 可用性验证: 携带 token 访问 /users/me
        client = auth_api.client
        client.set_token(data["access_token"])
        me = auth_api.me()
        client.set_token(None)
        assert_status(me, 200, "携带 token 获取用户信息")
        assert me.json()["username"] == user["username"]

    @allure.title("数据驱动-登录异常流: {case[name]}")
    @pytest.mark.parametrize("case", [
        pytest.param({"name": "密码错误", "password": "wrong_password"}, id="wrong_password"),
        pytest.param({"name": "用户不存在", "password": "123456"}, id="user_not_exist"),
    ])
    def test_login_failed(self, auth_api, user, case):
        # 用户不存在场景: 换成不存在的随机用户名
        username = unique_username() if case["name"] == "用户不存在" else user["username"]
        resp = auth_api.login(username, case["password"])
        assert_status(resp, 401, f"登录异常流: {case['name']}")
        assert resp.json()["detail"] == "Incorrect username or password"


@allure.feature("用户模块")
@allure.story("鉴权")
class TestAuthGuard:

    @allure.title("无 token 访问受保护接口返回 401")
    @pytest.mark.api
    def test_me_without_token(self, client):
        resp = client.get("/api/v1/users/me")
        assert_status(resp, 401, "无 token 访问")
        assert resp.json()["detail"] == "Not authenticated"

    @allure.title("伪造 token 访问受保护接口返回 401")
    @pytest.mark.api
    def test_me_with_invalid_token(self, client):
        client.set_token("invalid.token.value")
        resp = client.get("/api/v1/users/me")
        client.set_token(None)
        assert_status(resp, 401, "伪造 token 访问")
        assert resp.json()["detail"] == "Invalid or expired token"
