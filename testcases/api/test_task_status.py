"""任务状态流转接口测试

业务规则: pending -> in_progress -> done; done 为终态, 不可再流转
覆盖点: 合法流转、跨状态流转、幂等、违反业务规则 (409)、非法状态值 (422)、流转落库断言
"""
import allure
import pytest

from common.assertions import assert_status
from utils.data_factory import random_task


def _create_at_status(task_api, from_status: str) -> int:
    """前置: 创建任务并流转到指定初始状态"""
    created = task_api.create(random_task())
    assert_status(created, 201, f"前置创建任务(初始状态 {from_status})")
    task_id = created.json()["id"]
    if from_status == "in_progress":
        assert_status(task_api.change_status(task_id, "in_progress"), 200, "前置流转到进行中")
    elif from_status == "done":
        assert_status(task_api.change_status(task_id, "done"), 200, "前置流转到已完成")
    return task_id


@allure.feature("任务模块")
@allure.story("状态流转")
class TestTaskStatusFlow:

    @allure.title("数据驱动-状态流转: {case[name]}")
    @pytest.mark.api
    @pytest.mark.parametrize("case", [
        pytest.param({"name": "待办->进行中", "from_status": "pending", "to_status": "in_progress", "expected_status": 200}, id="pending_to_in_progress"),
        pytest.param({"name": "进行中->已完成", "from_status": "in_progress", "to_status": "done", "expected_status": 200}, id="in_progress_to_done"),
        pytest.param({"name": "待办->已完成(跨状态)", "from_status": "pending", "to_status": "done", "expected_status": 200}, id="pending_to_done"),
        pytest.param({"name": "已完成->已完成(幂等)", "from_status": "done", "to_status": "done", "expected_status": 200}, id="done_to_done"),
        pytest.param({"name": "已完成->待办(违反规则)", "from_status": "done", "to_status": "pending", "expected_status": 409}, id="done_to_pending"),
        pytest.param({"name": "已完成->进行中(违反规则)", "from_status": "done", "to_status": "in_progress", "expected_status": 409}, id="done_to_in_progress"),
        pytest.param({"name": "非法状态值", "from_status": "pending", "to_status": "unknown", "expected_status": 422}, id="invalid_status"),
    ])
    def test_status_flow(self, task_api, case):
        task_id = _create_at_status(task_api, case["from_status"])
        resp = task_api.change_status(task_id, case["to_status"])
        assert_status(resp, case["expected_status"], f"状态流转: {case['name']}")

        if case["expected_status"] == 200:
            assert resp.json()["status"] == case["to_status"]
        elif case["expected_status"] == 409:
            assert "final" in resp.json()["detail"]
            # 违反规则被拒绝后, 原状态保持不变
            assert task_api.get(task_id).json()["status"] == "done"

    @allure.title("状态流转落库断言: 响应与数据库状态一致")
    @pytest.mark.api
    def test_status_flow_persisted(self, task_api, db):
        created = task_api.create({"title": "流转落库任务"})
        assert_status(created, 201, "前置创建")
        task_id = created.json()["id"]

        assert_status(task_api.change_status(task_id, "in_progress"), 200, "流转到进行中")
        row = db.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
        assert row["status"] == "in_progress", "数据库状态未同步"

        assert_status(task_api.change_status(task_id, "done"), 200, "流转到已完成")
        row = db.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
        assert row["status"] == "done", "数据库状态未同步"

    @allure.title("完整生命周期: 创建->开始->完成->终态不可逆")
    @pytest.mark.api
    def test_full_lifecycle(self, task_api):
        """串联完整业务流, 验证生命周期每个环节"""
        created = task_api.create({"title": "生命周期任务", "priority": "high"})
        assert_status(created, 201, "1.创建")
        assert created.json()["status"] == "pending"
        task_id = created.json()["id"]

        started = task_api.change_status(task_id, "in_progress")
        assert_status(started, 200, "2.开始任务")
        assert started.json()["status"] == "in_progress"

        done = task_api.change_status(task_id, "done")
        assert_status(done, 200, "3.完成任务")
        assert done.json()["status"] == "done"

        revert = task_api.change_status(task_id, "pending")
        assert_status(revert, 409, "4.终态不可逆")
