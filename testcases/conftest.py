"""全局测试夹具与钩子

核心能力:
    1. 会话级自动拉起被测服务 (uvicorn 子进程 + 临时数据库), 测试与开发环境完全隔离
    2. 多环境配置加载 (--env / TEST_ENV), 支持指向外部已部署服务
    3. 统一 HTTP 客户端与 JWT 鉴权管理
    4. UI 用例失败自动截图 + 保存 Playwright Trace (可回放定位)
    5. Allure 报告增强: 失败附件自动归档
"""
import sqlite3
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

import allure
import pytest
import requests
import yaml
from loguru import logger

from api.auth_api import AuthApi
from api.task_api import StatsApi, TaskApi
from common.api_client import ApiClient
from common.logger import setup_logger
from config.settings import PROJECT_ROOT, get_settings
from utils.data_factory import random_password, unique_username

# ---------------------------------------------------------------------------
# 命令行参数
# ---------------------------------------------------------------------------
def pytest_addoption(parser):
    parser.addoption("--env", action="store", default=None,
                     help="测试环境: local / test / ci (默认取环境变量 TEST_ENV, 再默认 local)")


@pytest.fixture(scope="session")
def settings(pytestconfig):
    """全局测试配置 (Settings 对象)"""
    s = get_settings(pytestconfig.getoption("--env"))
    setup_logger(s.logs_dir, level=s.log_level)
    return s


# ---------------------------------------------------------------------------
# 被测服务管理
# ---------------------------------------------------------------------------
class _Server:
    """被测服务子进程包装: 启动 / 就绪探测 / 销毁"""

    def __init__(self, settings, tmp_db_path: Path, log_file: Path):
        self.settings = settings
        self.tmp_db_path = tmp_db_path
        self.log_file = log_file
        self.proc = None

    def start(self):
        env = {
            "TASKFLOW_DB": f"sqlite:///{self.tmp_db_path}",
            "TASKFLOW_SECRET_KEY": self.settings.secret_key or "taskflow-test-secret",
            "PYTHONIOENCODING": "utf-8",
        }
        kwargs = {"cwd": PROJECT_ROOT, "env": {**__import__("os").environ, **env},
                  "stdout": open(self.log_file, "w", encoding="utf-8"),
                  "stderr": subprocess.STDOUT}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", "127.0.0.1", "--port", str(urllib.parse.urlparse(self.settings.base_url).port)],
            **kwargs,
        )
        self._wait_ready()

    def _wait_ready(self, timeout: int = 30):
        """轮询健康检查接口直到服务就绪, 超时则输出服务日志并失败"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"被测服务启动失败, 日志: {self.log_file}")
            try:
                if requests.get(f"{self.settings.base_url}/health", timeout=2).status_code == 200:
                    logger.info(f"被测服务已就绪: {self.settings.base_url}")
                    return
            except requests.RequestException:
                pass
            time.sleep(0.5)
        raise TimeoutError(f"被测服务 {timeout}s 内未就绪, 请检查日志: {self.log_file}")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


@pytest.fixture(scope="session")
def app_server(settings, tmp_path_factory, worker_id):
    """会话级被测服务: 本地环境自动拉起 (临时数据库), 外部环境直接复用。

    并行执行 (pytest-xdist) 时每个 worker 独立起服务, 端口按 worker 编号
    偏移 (gw0 -> 8001, gw1 -> 8002 ...), 避免端口冲突。
    """
    if settings.use_external_server:
        logger.info(f"使用外部被测服务: {settings.base_url}")
        yield None
        return

    if worker_id != "master":
        offset = int(worker_id.replace("gw", ""))
        parsed = urllib.parse.urlparse(settings.base_url)
        settings.base_url = f"{parsed.scheme}://{parsed.hostname}:{parsed.port + offset}"

    db_dir = tmp_path_factory.mktemp("taskflow-db")
    tmp_db_path = db_dir / "taskflow.db"
    log_file = settings.logs_dir / f"server-{worker_id}.log"
    server = _Server(settings, tmp_db_path, log_file)
    logger.info(f"启动本地被测服务 [{worker_id}]: {settings.base_url} (uvicorn 子进程, 临时数据库)")
    server.start()
    yield server
    server.stop()


# ---------------------------------------------------------------------------
# 基础客户端 / 数据 fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def base_url(settings, app_server):
    """被测服务地址。依赖 app_server: 并行模式下端口偏移生效后再取值。"""
    return settings.base_url


@pytest.fixture(scope="session")
def client(base_url, settings, app_server):
    """会话级匿名客户端 (无 token), 仅用于注册/预置数据等无需登录的场景。

    依赖 app_server 保证任何用到网络的用例执行前被测服务已就绪。
    """
    c = ApiClient(base_url, timeout=settings.api_timeout)
    yield c
    c.close()


@pytest.fixture
def api_client_factory(base_url, settings):
    """函数级独立客户端工厂: 每次调用返回全新实例, 用例结束自动关闭。

    登录态用例必须使用独立实例 —— token 是客户端级别的状态,
    多个登录用户共享同一实例会导致 token 互相覆盖 (鉴权用例的核心隔离手段)。
    """
    created: list[ApiClient] = []

    def _make() -> ApiClient:
        c = ApiClient(base_url, timeout=settings.api_timeout)
        created.append(c)
        return c

    yield _make
    for c in created:
        c.close()


@pytest.fixture
def user(client):
    """每个用例一个独立随机用户, 保证数据隔离与用例可重复执行"""
    info = {"username": unique_username(), "password": random_password()}
    resp = AuthApi(client).register(info["username"], info["password"])
    assert resp.status_code == 201, f"测试用户注册失败: {resp.text}"
    info["user_id"] = resp.json()["id"]
    logger.info(f"创建测试用户: {info['username']} (id={info['user_id']})")
    return info


@pytest.fixture
def auth_client(api_client_factory, user):
    """已登录客户端: 独立实例携带当前用例用户的 JWT, 用例间天然隔离"""
    client = api_client_factory()
    resp = AuthApi(client).login(user["username"], user["password"])
    assert resp.status_code == 200, f"测试用户登录失败: {resp.text}"
    client.set_token(resp.json()["access_token"])
    return client


@pytest.fixture
def task_api(auth_client):
    return TaskApi(auth_client)


@pytest.fixture
def stats_api(auth_client):
    return StatsApi(auth_client)


@pytest.fixture
def anon_task_api(api_client_factory):
    """匿名客户端 (独立实例, 确保无 token 残留), 用于鉴权异常用例"""
    return TaskApi(api_client_factory())


@pytest.fixture
def ui_user(client):
    """UI 用例专用账号: 走 API 预置数据, UI 层只验证业务操作 (测试金字塔的经典分工)"""
    info = {"username": unique_username("ui"), "password": "UiTest@12345"}
    resp = AuthApi(client).register(info["username"], info["password"])
    assert resp.status_code == 201, f"UI 测试用户注册失败: {resp.text}"
    return info


# ---------------------------------------------------------------------------
# 数据库直连断言 (仅本地自起服务可用)
# ---------------------------------------------------------------------------
@pytest.fixture
def db(app_server):
    """直连被测服务临时 SQLite, 用于落库断言 (接口响应 + 持久化双重验证)"""
    if app_server is None:
        pytest.skip("外部服务模式下无法直连数据库, 跳过落库断言")
    conn = sqlite3.connect(app_server.tmp_db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# 测试数据文件加载
# ---------------------------------------------------------------------------
def _load_yaml(name: str) -> dict:
    with open(PROJECT_ROOT / "testdata" / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def users_data():
    return _load_yaml("users.yaml")


@pytest.fixture(scope="session")
def tasks_data():
    return _load_yaml("tasks.yaml")


# ---------------------------------------------------------------------------
# Playwright UI 测试配置: 无头模式 / 慢放 / 失败截图与 Trace
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def browser_name():
    return "chromium"


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args, settings):
    # 新版 Chromium 默认开启 HTTPS-Upgrade: 会把 http:// 非回环地址自动升级为 https://,
    # TLS 握手打到纯 HTTP 服务上会报 ERR_SSL_PROTOCOL_ERROR (详见 docs/test_plan.md BUG-09)。
    # 双保险:
    #   1. Docker/CI 环境 base_url 使用 *.localhost 域名 (app.localhost) —— Chromium 视其
    #      为回环地址天然豁免升级, 与浏览器版本无关 (实测 feature 开关名随版本变化, 不可靠);
    #   2. 本地回环地址 (127.0.0.1) 本身豁免; 仍显式禁用 HttpsUpgrades 特性兜底。
    # 注意: Chromium 会把 *.localhost 硬编码解析为 127.0.0.1 (豁免升级的代价),
    # 容器内必须用 host-resolver-rules 转回系统 DNS 才能解析到 app 容器。
    args = list(browser_type_launch_args.get("args", []))
    args.append("--host-resolver-rules=MAP app.localhost app")
    args.append("--disable-features=HttpsUpgrades")
    return {**browser_type_launch_args, "headless": settings.headless,
            "slow_mo": settings.slow_mo, "args": args}


@pytest.fixture
def page(browser, base_url, request):
    """UI 用例页面: 失败自动保存截图 + Playwright Trace (本地回放定位问题)"""
    context = browser.new_context(base_url=base_url, locale="zh-CN")
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    yield page

    if getattr(request.node, "_taskflow_failed", False):
        stem = _safe_name(request.node.nodeid)
        shot_dir = PROJECT_ROOT / "reports" / "screenshots"
        trace_dir = PROJECT_ROOT / "reports" / "traces"
        shot_dir.mkdir(parents=True, exist_ok=True)
        trace_dir.mkdir(parents=True, exist_ok=True)
        try:
            shot = shot_dir / f"{stem}.png"
            page.screenshot(path=shot, full_page=True)
            allure.attach.file(shot, name="失败截图", attachment_type=allure.attachment_type.PNG)
            logger.warning(f"用例失败截图已保存: {shot}")
        except Exception as e:  # 页面已关闭等极端情况不阻断清理
            logger.warning(f"截图失败: {e}")
        try:
            trace = trace_dir / f"{stem}.zip"
            context.tracing.stop(path=trace)
            logger.warning(f"用例 Trace 已保存 (playwright show-trace 可回放): {trace}")
        except Exception as e:
            logger.warning(f"Trace 保存失败: {e}")
    context.close()


def _safe_name(nodeid: str) -> str:
    """nodeid 转安全文件名"""
    return nodeid.replace("::", "__").replace("/", "_").replace("\\", "_")[:100]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """标记用例失败状态, 供 page fixture 决定是否截图/存 Trace"""
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        setattr(item, "_taskflow_failed", True)


def pytest_sessionfinish(session, exitstatus):
    """会话结束: 将完整执行日志归档到 Allure 报告 (无用例上下文时静默跳过)"""
    log_dir = PROJECT_ROOT / "logs"
    today_log = max(log_dir.glob("test-*.log"), key=lambda p: p.stat().st_mtime, default=None)
    if today_log:
        try:
            allure.attach.file(today_log, name="执行日志", attachment_type=allure.attachment_type.TEXT)
        except KeyError:
            logger.info(f"执行日志已保存: {today_log}")
