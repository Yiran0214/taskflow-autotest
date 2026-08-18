"""任务主页 Page Object: 任务增删改查、状态流转、统计看板"""
import allure
from playwright.sync_api import expect

from pages.base_page import BasePage

STATUS_LABEL = {"pending": "待办", "in_progress": "进行中", "done": "已完成"}


class TaskPage(BasePage):
    INDEX_URL = "/static/index.html"

    @allure.step("进入任务主页")
    def navigate(self):
        self.goto(self.INDEX_URL)
        expect(self.locator("task-add-btn")).to_be_visible()
        return self

    # ---------- 新建任务 ----------
    @allure.step("添加任务: {title}")
    def add_task(self, title: str, priority: str = "medium", due_date: str | None = None):
        self.locator("task-title-input").fill(title)
        self.locator("task-priority-select").select_option(priority)
        if due_date:
            self.locator("task-due-input").fill(due_date)
        self.locator("task-add-btn").click()
        return self

    def add_error(self) -> str:
        return self.locator("add-error").inner_text()

    # ---------- 任务列表 ----------
    def task_titles(self) -> list[str]:
        return self.locator("task-title").all_inner_texts()

    def task_item(self, title: str):
        return self.page.locator('[data-testid="task-item"]', has_text=title)

    def expect_task_visible(self, title: str):
        expect(self.task_item(title)).to_be_visible()

    def expect_task_not_visible(self, title: str):
        expect(self.task_item(title)).to_have_count(0)

    # ---------- 状态流转与操作 ----------
    @allure.step("开始任务: {title}")
    def start_task(self, title: str):
        self.task_item(title).get_by_test_id("task-start-btn").click()

    @allure.step("完成任务: {title}")
    def complete_task(self, title: str):
        self.task_item(title).get_by_test_id("task-done-btn").click()

    @allure.step("删除任务: {title}")
    def delete_task(self, title: str, confirm: bool = True):
        if confirm:
            self.page.once("dialog", lambda d: d.accept())
        self.task_item(title).get_by_test_id("task-delete-btn").click()

    @allure.step("编辑任务标题: {title} -> {new_title}")
    def edit_title(self, title: str, new_title: str):
        self.task_item(title).get_by_test_id("task-edit-btn").click()
        self.locator("task-edit-input").fill(new_title)
        self.locator("task-edit-save").click()

    def task_status(self, title: str) -> str:
        return self.task_item(title).get_by_test_id("task-status").inner_text()

    def expect_task_status(self, title: str, status: str):
        expect(self.task_item(title).get_by_test_id("task-status")).to_have_text(STATUS_LABEL[status])

    # ---------- 筛选 ----------
    @allure.step("按状态筛选: {filter_name}")
    def filter_by(self, filter_name: str):
        self.locator(f"filter-{filter_name}").click()

    def expect_empty_tip(self):
        expect(self.locator("empty-tip")).to_be_visible()

    # ---------- 统计看板 ----------
    def stats(self) -> dict:
        return {
            "total": self.locator("stats-total").inner_text(),
            "pending": self.locator("stats-pending").inner_text(),
            "in_progress": self.locator("stats-in_progress").inner_text(),
            "done": self.locator("stats-done").inner_text(),
            "completion": self.locator("stats-completion").inner_text(),
        }

    def expect_stats(self, **kwargs):
        """断言统计看板数值 (自动等待异步渲染), 如 expect_stats(total='2', done='1')"""
        for key, value in kwargs.items():
            expect(self.locator(f"stats-{key}")).to_have_text(str(value), timeout=5_000)
        return self

    # ---------- 会话 ----------
    def logout(self):
        self.locator("logout-btn").click()
        self.wait_url("/static/login.html")
