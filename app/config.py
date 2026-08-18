"""TaskFlow 应用配置。

所有配置项均支持通过环境变量覆盖,便于测试环境与生产环境隔离:
    - TASKFLOW_DB: SQLite 数据库地址 (测试时指向临时目录,避免污染开发数据)
    - TASKFLOW_SECRET_KEY: JWT 签名密钥
    - TASKFLOW_TOKEN_EXPIRE_MINUTES: Token 有效期(分钟)
"""
import os


class AppConfig:
    DATABASE_URL: str = os.getenv("TASKFLOW_DB", "sqlite:///./taskflow.db")
    SECRET_KEY: str = os.getenv("TASKFLOW_SECRET_KEY", "taskflow-dev-secret-key")
    TOKEN_EXPIRE_MINUTES: int = int(os.getenv("TASKFLOW_TOKEN_EXPIRE_MINUTES", "60"))
    ALGORITHM: str = "HS256"


config = AppConfig()
