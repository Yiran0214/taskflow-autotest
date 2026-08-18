"""测试框架配置加载: YAML 多环境 + 环境变量覆盖 + 命令行 --env 优先"""
import os
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "config.yaml"


class Settings:
    """读取 config.yaml 中指定环境的小节, 支持 TEST_<KEY> 环境变量覆盖"""

    def __init__(self, env: str = "local"):
        with open(CONFIG_FILE, encoding="utf-8") as f:
            all_envs = yaml.safe_load(f)
        if env not in all_envs:
            raise ValueError(f"未知环境 '{env}', 可用环境: {list(all_envs)}")
        self.env = env
        data = all_envs[env]
        for key, value in data.items():
            env_var = os.getenv(f"TEST_{key.upper()}")
            setattr(self, key, env_var if env_var is not None else value)

    @property
    def reports_dir(self) -> Path:
        return PROJECT_ROOT / "reports"

    @property
    def logs_dir(self) -> Path:
        return PROJECT_ROOT / "logs"


def get_settings(env: str | None = None) -> Settings:
    """环境优先级: 显式传入 > 环境变量 TEST_ENV > 默认 local"""
    return Settings(env or os.getenv("TEST_ENV", "local"))
