#!/usr/bin/env python3
"""TaskFlow 自动化测试框架统一入口

用法示例:
    python run.py test                      # 执行全部用例 (API + UI)
    python run.py test --type api           # 仅执行 API 用例
    python run.py test --type web           # 仅执行 UI 用例
    python run.py test --env test           # 指定环境 (local/test/ci)
    python run.py test --parallel 4 --reruns 2   # 并行执行 + 失败重试
    python run.py test --headed             # UI 有头模式 (本地调试)
    python run.py server                    # 单独启动被测服务 (开发调试)
    python run.py report                    # 打开 Allure 报告 (需本机安装 allure)
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def cmd_test(args):
    pytest_args = [sys.executable, "-m", "pytest"]

    if args.type == "api":
        pytest_args.append("testcases/api")
    elif args.type == "web":
        pytest_args.append("testcases/ui")
    else:
        pytest_args.append("testcases")

    if args.env:
        pytest_args += ["--env", args.env]
    if args.parallel:
        pytest_args += ["-n", str(args.parallel), "--dist", "loadscope"]
    if args.reruns:
        pytest_args += ["--reruns", str(args.reruns), "--reruns-delay", "1"]

    env = dict(os.environ)
    if args.headed:
        env["TEST_HEADLESS"] = "false"
    # Windows 控制台 GBK 编码下强制子进程输出 UTF-8, 避免中文/符号打印异常
    env.setdefault("PYTHONIOENCODING", "utf-8")

    print(f"\n>> 执行命令: {' '.join(pytest_args)}\n")
    return subprocess.run(pytest_args, cwd=PROJECT_ROOT, env=env).returncode


def cmd_server(args):
    print(">> 启动 TaskFlow 被测服务: http://127.0.0.1:8001 (Ctrl+C 停止)")
    return subprocess.run(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(args.port)],
        cwd=PROJECT_ROOT,
    ).returncode


def cmd_report(args):
    results = PROJECT_ROOT / "reports" / "allure-results"
    if not list(results.glob("*.json")):
        print("[x] 未找到 allure-results 数据, 请先执行: python run.py test")
        return 1
    print(">> 生成并打开 Allure 报告 (Ctrl+C 停止服务后报告页面会关闭)")
    return subprocess.run(
        ["allure", "serve", str(results), "--port", str(args.port)]
    ).returncode


def main():
    parser = argparse.ArgumentParser(description="TaskFlow 自动化测试框架")
    sub = parser.add_subparsers(dest="command", required=True)

    p_test = sub.add_parser("test", help="执行自动化测试")
    p_test.add_argument("--type", choices=["api", "web", "all"], default="all", help="用例类型 (默认 all)")
    p_test.add_argument("--env", default=None, help="测试环境: local/test/ci")
    p_test.add_argument("--parallel", type=int, default=None, help="并行 worker 数 (pytest-xdist)")
    p_test.add_argument("--reruns", type=int, default=None, help="失败重试次数")
    p_test.add_argument("--headed", action="store_true", help="UI 有头模式运行")
    p_test.set_defaults(func=cmd_test)

    p_server = sub.add_parser("server", help="启动被测服务")
    p_server.add_argument("--port", type=int, default=8001)
    p_server.set_defaults(func=cmd_server)

    p_report = sub.add_parser("report", help="生成并打开 Allure 报告")
    p_report.add_argument("--port", type=int, default=8899)
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
