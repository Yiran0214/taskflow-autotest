"""TaskFlow 性能/压力测试脚本 (Locust)

运行方式 (先启动被测服务):
    python run.py server &
    locust -f performance_tests/locustfile.py --host http://127.0.0.1:8001
    # 浏览器访问 http://localhost:8089 配置并发数

无界面模式 (适合 CI / 服务器):
    locust -f performance_tests/locustfile.py --host http://127.0.0.1:8001 \
        --headless -u 50 -r 10 -t 2m --html reports/locust-report.html

场景说明:
    - 每个虚拟用户 on_start 时注册/登录, 模拟真实用户会话
    - 读写按 4:2:1 权重配比: 查询列表 > 创建任务 > 查询统计
    - 每 10 次列表查询中约有 1 次任务生命周期 (创建->完成->删除), 模拟完整用户旅程
"""
import random
import string

from locust import HttpUser, between, task


class TaskFlowUser(HttpUser):
    """模拟一个已登录的待办系统用户"""

    wait_time = between(1, 3)  # 用户操作间隔 1-3 秒

    def on_start(self):
        """用户会话初始化: 注册新用户并登录获取 token"""
        self.username = "perf_" + "".join(random.choices(string.ascii_lowercase, k=10))
        self.password = "Perf@12345"
        resp = self.client.post("/api/v1/auth/register",
                                json={"username": self.username, "password": self.password})
        if resp.status_code not in (201, 409):  # 409=已存在(重复压测), 两种都继续
            resp.failure(f"注册失败: {resp.status_code} {resp.text}")
            return
        login = self.client.post("/api/v1/auth/login",
                                 json={"username": self.username, "password": self.password})
        if login.status_code != 200:
            login.failure(f"登录失败: {login.status_code}")
            return
        self.client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    @task(4)
    def query_task_list(self):
        """高频场景: 查询任务列表"""
        with self.client.get("/api/v1/tasks", name="查询任务列表", catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"期望 200, 实际 {r.status_code}")

    @task(2)
    def create_task(self):
        """创建任务"""
        payload = {"title": f"压测任务-{random.randint(1, 99999)}",
                   "priority": random.choice(["low", "medium", "high"])}
        with self.client.post("/api/v1/tasks", json=payload, name="创建任务", catch_response=True) as r:
            if r.status_code != 201:
                r.failure(f"期望 201, 实际 {r.status_code}")

    @task(1)
    def query_stats(self):
        """查询统计看板"""
        with self.client.get("/api/v1/stats/summary", name="查询统计", catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"期望 200, 实际 {r.status_code}")

    @task(1)
    def task_lifecycle(self):
        """低频场景: 完整任务生命周期 (创建->完成->删除)"""
        created = self.client.post("/api/v1/tasks", json={"title": "生命周期压测"},
                                   name="生命周期-创建", catch_response=True)
        if created.status_code != 201:
            created.failure(f"创建失败: {created.status_code}")
            return
        task_id = created.json()["id"]
        self.client.patch(f"/api/v1/tasks/{task_id}/status", json={"status": "done"},
                          name="生命周期-完成")
        self.client.delete(f"/api/v1/tasks/{task_id}", name="生命周期-删除")
