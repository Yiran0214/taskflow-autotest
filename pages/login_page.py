"""登录/注册页 Page Object"""
import allure
from playwright.sync_api import expect

from pages.base_page import BasePage


class LoginPage(BasePage):
    LOGIN_URL = "/static/login.html"

    @allure.step("进入登录页")
    def navigate(self):
        self.goto(self.LOGIN_URL)
        expect(self.locator("login-submit")).to_be_visible()
        return self

    @allure.step("切换到注册表单")
    def switch_to_register(self):
        self.locator("tab-register").click()
        return self

    @allure.step("登录: {username}")
    def login(self, username: str, password: str):
        self.locator("login-username").fill(username)
        self.locator("login-password").fill(password)
        self.locator("login-submit").click()
        return self

    @allure.step("注册: {username}")
    def register(self, username: str, password: str):
        self.locator("register-username").fill(username)
        self.locator("register-password").fill(password)
        self.locator("register-submit").click()
        return self

    def error_message(self) -> str:
        return self.locator("auth-error").inner_text()

    def expect_logged_in(self):
        """登录成功应跳转到任务主页"""
        self.wait_url("/static/index.html")
        expect(self.locator("logout-btn")).to_be_visible()
