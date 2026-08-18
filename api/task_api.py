"""任务接口封装层"""
import allure

from common.api_client import ApiClient


class TaskApi:
    def __init__(self, client: ApiClient):
        self.client = client

    @allure.step("创建任务: {payload}")
    def create(self, payload: dict):
        return self.client.post("/api/v1/tasks", json=payload)

    @allure.step("获取任务详情: id={task_id}")
    def get(self, task_id: int):
        return self.client.get(f"/api/v1/tasks/{task_id}")

    @allure.step("查询任务列表")
    def list(self, **params):
        """注意: allure.step 标题按调用时实参插值, 参数可能缺省, 故不在标题中引用"""
        return self.client.get("/api/v1/tasks", params=params)

    @allure.step("全量更新任务: id={task_id}, {payload}")
    def update(self, task_id: int, payload: dict):
        return self.client.put(f"/api/v1/tasks/{task_id}", json=payload)

    @allure.step("部分更新任务: id={task_id}, {payload}")
    def patch(self, task_id: int, payload: dict):
        return self.client.patch(f"/api/v1/tasks/{task_id}", json=payload)

    @allure.step("变更任务状态: id={task_id} -> {status}")
    def change_status(self, task_id: int, status: str):
        return self.client.patch(f"/api/v1/tasks/{task_id}/status", json={"status": status})

    @allure.step("删除任务: id={task_id}")
    def delete(self, task_id: int):
        return self.client.delete(f"/api/v1/tasks/{task_id}")

    @allure.step("清理用户全部任务")
    def cleanup_all(self):
        """删除当前用户所有任务 (用例后置清理)"""
        resp = self.list(size=100)
        if resp.status_code == 200:
            for item in resp.json()["items"]:
                self.client.delete(f"/api/v1/tasks/{item['id']}")


class StatsApi:
    def __init__(self, client: ApiClient):
        self.client = client

    @allure.step("获取任务统计汇总")
    def summary(self):
        return self.client.get("/api/v1/stats/summary")
