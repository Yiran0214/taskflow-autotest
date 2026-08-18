"""数据库引擎与会话管理 (SQLAlchemy + SQLite)"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import config

# check_same_thread=False: FastAPI 多线程处理请求时允许跨线程使用同一连接
engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI 依赖: 每个请求一个独立会话,请求结束自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
