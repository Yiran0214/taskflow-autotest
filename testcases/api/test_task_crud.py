"""任务模块 CRUD 接口测试

覆盖点:
    - 创建: 正常流、默认值、标题长度边界、非法优先级、非法日期
    - 查询: 详情、列表分页、状态/优先级筛选、异常参数
    - 更新: PUT 全量 (字段重置) / PATCH 部分 (字段保留)
    - 删除: 正常流、重复删除、删除后不可见
    - 落库断言: 接口响应与数据库持久化双重验证
"""
import allure
import pytest

from common.assertions import assert_status, assert_task_shape, validate_schema
from utils.data_factory import boundary_title, random_task

LIST_SCHEMA = {
    "type": "object",
    "required": ["items", "total", "page", "size", "pages"],
    "properties": {
        "items": {"type": "list"},
        "total": {"type": "int"},
        "page": {"type": "int"},
        "size": {"type": "int"},
        "pages": {"type": "int"},
    },
}


@allure.feature("任务模块")
@allure.story("创建任务")
class TestCreateTask:

    @allure.title("创建任务成功: 返回完整字段且默认值正确")
    @pytest.mark.api
    def test_create_success_with_defaults(self, task_api):
        resp = task_api.create({"title": "默认值校验任务"})
        assert_status(resp, 201, "创建任务")
        data = resp.json()
        assert data["title"] == "默认值校验任务"
        assert data["priority"] == "medium"   # 默认中优先级
        assert data["status"] == "pending"    # 默认待办
        assert data["description"] is None
        assert data["due_date"] is None

    @allure.title("创建任务成功: 全字段回显一致")
    @pytest.mark.api
    def test_create_success_full_fields(self, task_api):
        payload = random_task({"priority": "high", "due_date": "2026-12-31"})
        resp = task_api.create(payload)
        assert_status(resp, 201, "全字段创建")
        data = resp.json()
        assert_task_shape(data)
        assert data["title"] == payload["title"]
        assert data["description"] == payload["description"]
        assert data["priority"] == "high"
        assert data["due_date"] == "2026-12-31"

    @allure.title("创建任务落库断言: 数据库持久化与响应一致")
    @pytest.mark.api
    def test_create_persisted_in_db(self, task_api, db, user):
        resp = task_api.create({"title": "落库校验任务"})
        assert_status(resp, 201, "创建任务")
        row = db.execute(
            "SELECT title, status, user_id FROM tasks WHERE id = ?", (resp.json()["id"],)
        ).fetchone()
        assert row is not None, "任务未持久化到数据库"
        assert row["title"] == "落库校验任务"
        assert row["status"] == "pending"
        assert row["user_id"] == user["user_id"], "任务归属用户错误"

    @allure.title("数据驱动-标题长度边界: {case[name]}")
    @pytest.mark.api
    @pytest.mark.parametrize("case", [
        pytest.param({"name": "最短1字符", "title": "A", "expected_status": 201}, id="title_min_1"),
        pytest.param({"name": "最长100字符", "title": None, "expected_status": 201}, id="title_max_100"),
        pytest.param({"name": "超长101字符", "title": None, "expected_status": 422}, id="title_over_101"),
        pytest.param({"name": "空字符串", "title": "", "expected_status": 422}, id="title_empty"),
    ])
    def test_create_title_boundary(self, task_api, case):
        # 动态构造 100/101 字符标题
        if case["title"] is None:
            title = boundary_title(100 if case["name"] == "最长100字符" else 101)
        else:
            title = case["title"]
        resp = task_api.create({"title": title})
        assert_status(resp, case["expected_status"], f"标题边界: {case['name']}")

    @allure.title("数据驱动-非法入参创建: {case[name]}")
    @pytest.mark.api
    @pytest.mark.parametrize("case", [
        pytest.param({"name": "缺少标题字段", "payload": {"priority": "high"}}, id="missing_title"),
        pytest.param({"name": "空 Payload", "payload": {}}, id="empty_payload"),
        pytest.param({"name": "非法优先级", "payload": {"title": "t", "priority": "urgent"}}, id="bad_priority"),
        pytest.param({"name": "非法日期格式", "payload": {"title": "t", "due_date": "2026/12/31"}}, id="bad_date_format"),
        pytest.param({"name": "不存在的日期", "payload": {"title": "t", "due_date": "2026-02-30"}}, id="impossible_date"),
        pytest.param({"name": "描述超长501字符", "payload": {"title": "t", "description": "x" * 501}}, id="desc_over_500"),
    ])
    def test_create_invalid_payload(self, task_api, case):
        resp = task_api.create(case["payload"])
        assert_status(resp, 422, f"非法入参: {case['name']}")


@allure.feature("任务模块")
@allure.story("查询任务")
class TestQueryTask:

    @allure.title("查询任务详情成功")
    @pytest.mark.api
    def test_get_task(self, task_api):
        created = task_api.create(random_task())
        assert_status(created, 201, "前置创建")
        resp = task_api.get(created.json()["id"])
        assert_status(resp, 200, "查询详情")
        assert resp.json()["id"] == created.json()["id"]

    @allure.title("查询不存在的任务返回 404")
    @pytest.mark.api
    def test_get_task_not_found(self, task_api):
        resp = task_api.get(999999)
        assert_status(resp, 404, "查询不存在任务")
        assert resp.json()["detail"] == "Task not found"

    @allure.title("列表查询: 结构校验、总数与分页正确")
    @pytest.mark.api
    def test_list_pagination(self, task_api):
        for i in range(5):
            resp = task_api.create({"title": f"分页任务{i}"})
            assert_status(resp, 201, f"前置创建任务{i}")
        # 默认分页: size=10
        resp = task_api.list()
        assert_status(resp, 200, "默认分页查询")
        validate_schema(resp.json(), LIST_SCHEMA)
        assert resp.json()["total"] == 5
        # 每页 2 条, 共 3 页
        page1 = task_api.list(page=1, size=2).json()
        assert len(page1["items"]) == 2 and page1["pages"] == 3
        assert page1["items"][0]["title"] == "分页任务4"  # 按 id 倒序
        # 第 3 页仅 1 条
        page3 = task_api.list(page=3, size=2).json()
        assert len(page3["items"]) == 1

    @allure.title("列表筛选: 按状态和优先级过滤")
    @pytest.mark.api
    def test_list_filter(self, task_api):
        for payload in [
            {"title": "待办-高优先级", "priority": "high"},
            {"title": "待办-低优先级", "priority": "low"},
            {"title": "已完成任务", "priority": "medium"},
        ]:
            assert_status(task_api.create(payload), 201, "前置创建")
        # 把最后一个任务标记完成
        all_tasks = task_api.list().json()["items"]
        done_id = next(t["id"] for t in all_tasks if t["title"] == "已完成任务")
        assert_status(task_api.change_status(done_id, "done"), 200, "前置状态变更")

        pending = task_api.list(status="pending").json()
        assert pending["total"] == 2 and all(t["status"] == "pending" for t in pending["items"])
        high = task_api.list(priority="high").json()
        assert high["total"] == 1 and high["items"][0]["title"] == "待办-高优先级"
        done = task_api.list(status="done").json()
        assert done["total"] == 1 and done["items"][0]["title"] == "已完成任务"

    @allure.title("列表查询非法分页参数返回 422")
    @pytest.mark.api
    def test_list_invalid_pagination(self, task_api):
        assert_status(task_api.list(page=0), 422, "page=0")
        assert_status(task_api.list(size=101), 422, "size=101")


@allure.feature("任务模块")
@allure.story("更新任务")
class TestUpdateTask:

    @allure.title("PUT 全量更新: 未传字段被重置为默认值")
    @pytest.mark.api
    def test_put_full_update_resets_fields(self, task_api):
        created = task_api.create(random_task({"description": "原始描述"}))
        assert_status(created, 201, "前置创建")
        task_id = created.json()["id"]

        resp = task_api.update(task_id, {"title": "更新后标题", "priority": "low"})
        assert_status(resp, 200, "全量更新")
        data = resp.json()
        assert data["title"] == "更新后标题"
        assert data["priority"] == "low"
        assert data["description"] is None, "PUT 未传 description 应被重置"
        assert data["due_date"] is None

    @allure.title("PATCH 部分更新: 仅更新指定字段, 其余保留")
    @pytest.mark.api
    def test_patch_partial_update_keeps_fields(self, task_api):
        created = task_api.create(random_task({"description": "保留的描述", "priority": "high"}))
        assert_status(created, 201, "前置创建")
        task_id = created.json()["id"]

        resp = task_api.patch(task_id, {"title": "部分更新标题"})
        assert_status(resp, 200, "部分更新")
        data = resp.json()
        assert data["title"] == "部分更新标题"
        assert data["description"] == "保留的描述", "PATCH 未传 description 应保留"
        assert data["priority"] == "high"

    @allure.title("更新不存在的任务返回 404")
    @pytest.mark.api
    def test_update_not_found(self, task_api):
        assert_status(task_api.patch(999999, {"title": "x"}), 404, "PATCH 不存在任务")
        assert_status(task_api.update(999999, {"title": "x"}), 404, "PUT 不存在任务")


@allure.feature("任务模块")
@allure.story("删除任务")
class TestDeleteTask:

    @allure.title("删除任务成功且数据库记录被移除")
    @pytest.mark.api
    def test_delete_success(self, task_api, db):
        created = task_api.create({"title": "待删除任务"})
        assert_status(created, 201, "前置创建")
        task_id = created.json()["id"]

        resp = task_api.delete(task_id)
        assert_status(resp, 204, "删除任务")

        assert_status(task_api.get(task_id), 404, "删除后查询")
        row = db.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
        assert row is None, "删除后数据库仍残留记录"

    @allure.title("重复删除同一任务返回 404")
    @pytest.mark.api
    def test_delete_twice(self, task_api):
        created = task_api.create({"title": "重复删除任务"})
        assert_status(created, 201, "前置创建")
        task_id = created.json()["id"]
        assert_status(task_api.delete(task_id), 204, "首次删除")
        assert_status(task_api.delete(task_id), 404, "重复删除")
