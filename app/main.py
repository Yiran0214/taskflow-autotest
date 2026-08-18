"""TaskFlow 待办系统 FastAPI 入口

启动方式:
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.database import engine
from app.models import Base
from app.routers import stats, tasks, users

STATIC_DIR = "app/static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 启动时自动建表
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="TaskFlow API",
    description="待办任务管理系统 (被测系统)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(tasks.router)
app.include_router(stats.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    """根路径重定向到登录页"""
    return RedirectResponse("/static/login.html")


@app.get("/health")
def health():
    """健康检查接口 (供测试框架就绪探测使用)"""
    return {"status": "ok"}
