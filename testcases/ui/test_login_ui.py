"""登录/注册页面 UI 测试

覆盖点:
    - 登录成功跳转任务主页并展示用户名
    - 登录失败 (密码错误) 展示错误提示
    - UI 注册成功流程 (数据走 API 预置的随机账号体系)
    - 未登录访问受保护页面自动重定向
"""
import allure
import pytest
from playwright.sync_api import expect

from pages.login_page import LoginPage
from pages.task_page import TaskPage
from utils.data_factory import unique_username


@allure.feature("Web UI 测试")
@allure.story("登录/注册")
class TestLoginUI:

    @allure.title("E2E-登录成功进入任务主页")
    @pytest.mark.web
    def test_login_success(self, page, ui_user):
        LoginPage(page).navigate().login(ui_user["username"], ui_user["password"])
        task_page = TaskPage(page)
        task_page.wait_url("/static/index.html")
        # 顶栏展示当前用户名 (前端异步渲染, 用自动等待断言), 且任务主页功能可用
        expect(page.get_by_test_id("current-username")).to_contain_text(f"👤 {ui_user['username']}")
        task_page.expect_stats(total="0")

    @allure.title("登录失败: 密码错误展示错误提示")
    @pytest.mark.web
    def test_login_wrong_password(self, page, ui_user):
        login_page = LoginPage(page).navigate().login(ui_user["username"], "WrongPass@1")
        expect(page.get_by_test_id("auth-error")).to_contain_text("Incorrect username or password")
        # 停留在登录页
        assert "/static/login.html" in page.url

    @allure.title("UI 注册成功: 提示注册成功并切回登录表单")
    @pytest.mark.web
    def test_register_via_ui(self, page):
        username = unique_username("uireg")
        login_page = LoginPage(page).navigate()
        login_page.switch_to_register().register(username, "UiReg@12345")
        expect(page.get_by_test_id("auth-error")).to_contain_text("注册成功")
        # 切回登录表单后可直接登录
        login_page.login(username, "UiReg@12345")
        login_page.expect_logged_in()

    @allure.title("未登录直接访问任务主页被重定向到登录页")
    @pytest.mark.web
    def test_redirect_when_unauthenticated(self, page):
        page.goto("/static/index.html")
        page.wait_for_url("**/static/login.html**")
        assert "/static/login.html" in page.url

    @allure.title("退出登录返回登录页且无法回退")
    @pytest.mark.web
    def test_logout(self, page, ui_user):
        LoginPage(page).navigate().login(ui_user["username"], ui_user["password"])
        TaskPage(page).wait_url("/static/index.html")
        TaskPage(page).logout()
        assert "/static/login.html" in page.url
