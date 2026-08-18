"""页面对象基类: 通用导航与等待能力"""
import allure
from playwright.sync_api import Page


class BasePage:
    def __init__(self, page: Page):
        self.page = page

    @allure.step("打开页面: {url}")
    def goto(self, url: str):
        self.page.goto(url)
        return self

    def locator(self, testid: str):
        """按 data-testid 定位元素 (前后端约定的稳定选择器)"""
        return self.page.get_by_test_id(testid)

    def wait_url(self, fragment: str, timeout: int = 10_000):
        self.page.wait_for_url(f"**{fragment}**", timeout=timeout)
