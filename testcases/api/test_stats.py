"""统计汇总接口测试

覆盖点:
    - 新用户统计全零 (边界: 无数据)
    - 多状态任务统计准确性 (含逾期任务判定)
    - 完成率计算精度 (四舍五入)
    - 统计与任务增删改的联动
"""
import allure
import pytest

from common.assertions import assert_status, validate_schema

STATS_SCHEMA = {
    "type": "object",
    "required": ["total", "pending", "in_progress", "done", "overdue", "completion_rate"],
    "properties": {
        "total": {"type": "int"},
        "pending": {"type": "int"},
        "in_progress": {"type": "int"},
        "done": {"type": "int"},
        "overdue": {"type": "int"},
        "completion_rate": {"type": "float"},
    },
}


@allure.feature("统计模块")
@allure.story("任务汇总")
class TestStats:

    @allure.title("新用户统计: 无数据时全零且完成率为 0")
    @pytest.mark.api
    def test_stats_empty(self, stats_api):
        resp = stats_api.summary()
        assert_status(resp, 200, "空数据统计")
        validate_schema(resp.json(), STATS_SCHEMA)
        assert resp.json() == {
            "total": 0, "pending": 0, "in_progress": 0,
            "done": 0, "overdue": 0, "completion_rate": 0.0,
        }

    @allure.title("多状态任务统计准确 (含逾期任务)")
    @pytest.mark.api
    def test_stats_with_tasks(self, stats_api, task_api):
        # 待办(已逾期) + 进行中 + 已完成
        assert_status(task_api.create({"title": "逾期待办", "due_date": "2020-01-01"}), 201, "创建逾期任务")
        assert_status(task_api.create({"title": "正常待办"}), 201, "创建待办任务")
        started = task_api.create({"title": "进行中任务"})
        assert_status(task_api.change_status(started.json()["id"], "in_progress"), 200, "流转进行中")
        done = task_api.create({"title": "已完成任务"})
        assert_status(task_api.change_status(done.json()["id"], "done"), 200, "流转已完成")

        resp = stats_api.summary()
        assert_status(resp, 200, "统计汇总")
        data = resp.json()
        assert data["total"] == 4
        assert data["pending"] == 2
        assert data["in_progress"] == 1
        assert data["done"] == 1
        assert data["overdue"] == 1, "仅逾期未完成任务计入 overdue"
        assert data["completion_rate"] == 0.25

    @allure.title("统计联动: 完成任务后统计实时更新")
    @pytest.mark.api
    def test_stats_sync_after_status_change(self, stats_api, task_api):
        created = task_api.create({"title": "联动任务"})
        assert_status(created, 201, "创建任务")
        assert stats_api.summary().json()["done"] == 0

        assert_status(task_api.change_status(created.json()["id"], "done"), 200, "完成任务")
        data = stats_api.summary().json()
        assert data["done"] == 1
        assert data["completion_rate"] == 1.0

        assert_status(task_api.delete(created.json()["id"]), 204, "删除任务")
        assert stats_api.summary().json()["total"] == 0

    @allure.title("无 token 访问统计接口返回 401")
    @pytest.mark.api
    def test_stats_without_token(self, client):
        resp = client.get("/api/v1/stats/summary")
        assert_status(resp, 401, "无 token 访问统计")
