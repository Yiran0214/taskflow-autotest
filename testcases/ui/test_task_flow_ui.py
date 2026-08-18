"""任务管理端到端 (E2E) UI 测试

覆盖完整用户旅程:
    登录 -> 创建任务 -> 开始 -> 完成 -> 编辑 -> 筛选 -> 删除
以及关键异常交互: 空标题拦截、统计看板实时联动
"""
import allure
import pytest
from playwright.sync_api import expect

from pages.login_page import LoginPage
from pages.task_page import TaskPage


@pytest.fixture
def task_page(page, ui_user):
    """前置: 通过真实登录进入任务主页"""
    LoginPage(page).navigate().login(ui_user["username"], ui_user["password"])
    tp = TaskPage(page)
    tp.wait_url("/static/index.html")
    return tp


@allure.feature("Web UI 测试")
@allure.story("任务管理端到端")
class TestTaskFlowUI:

    @allure.title("E2E-完整任务生命周期: 创建->开始->完成->编辑->筛选->删除")
    @pytest.mark.web
    def test_full_task_lifecycle(self, task_page):
        # 1. 创建高优先级任务
        task_page.add_task("学习 Playwright 自动化", priority="high")
        task_page.expect_task_visible("学习 Playwright 自动化")
        task_page.expect_stats(total="1", pending="1", completion="0%")

        # 2. 开始任务: 状态流转为进行中
        task_page.start_task("学习 Playwright 自动化")
        task_page.expect_task_status("学习 Playwright 自动化", "in_progress")
        task_page.expect_stats(in_progress="1")

        # 3. 完成任务: 状态流转为已完成, 完成率 100%
        task_page.complete_task("学习 Playwright 自动化")
        task_page.expect_task_status("学习 Playwright 自动化", "done")
        task_page.expect_stats(done="1", completion="100%")

        # 4. 编辑任务标题
        task_page.edit_title("学习 Playwright 自动化", "学习 Playwright 自动化(已完成打卡)")
        task_page.expect_task_visible("学习 Playwright 自动化(已完成打卡)")

        # 5. 筛选: 已完成列表可见, 待办列表为空
        task_page.filter_by("done")
        task_page.expect_task_visible("学习 Playwright 自动化(已完成打卡)")
        task_page.filter_by("pending")
        task_page.expect_empty_tip()

        # 6. 删除任务: 回到全部列表删除, 统计归零
        task_page.filter_by("all")
        task_page.delete_task("学习 Playwright 自动化(已完成打卡)")
        task_page.expect_task_not_visible("学习 Playwright 自动化(已完成打卡)")
        task_page.expect_stats(total="0", completion="0%")

    @allure.title("E2E-多任务管理与统计联动")
    @pytest.mark.web
    def test_multi_tasks_and_stats(self, task_page):
        task_page.add_task("写测试计划", priority="high")
        task_page.add_task("评审用例", priority="medium")
        task_page.add_task("输出测试报告", priority="low")
        task_page.expect_stats(total="3", pending="3")

        # 完成其中两个
        task_page.complete_task("写测试计划")
        task_page.complete_task("评审用例")
        task_page.expect_stats(total="3", done="2", completion="67%")

        # 待办筛选: 仅剩未完成的任务 (自动等待筛选结果渲染)
        task_page.filter_by("pending")
        expect(task_page.locator("task-title")).to_have_text(["输出测试报告"])

    @allure.title("新建任务为空标题时被拦截并提示")
    @pytest.mark.web
    def test_add_empty_title_blocked(self, task_page):
        task_page.locator("task-add-btn").click()
        assert "请输入任务标题" in task_page.add_error()
        task_page.expect_stats(total="0")

    @allure.title("E2E-删除操作确认弹窗可取消")
    @pytest.mark.web
    def test_delete_with_cancel(self, task_page):
        task_page.add_task("不删除的任务")
        task_page.expect_task_visible("不删除的任务")
        task_page.delete_task("不删除的任务", confirm=False)
        # 取消后任务仍在
        task_page.expect_task_visible("不删除的任务")
        task_page.expect_stats(total="1")
