"""任务模块: CRUD + 状态流转 (含业务规则)"""
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Task, TaskPriority, TaskStatus, User
from app.routers.users import get_current_user
from app.schemas import (
    TaskCreate,
    TaskListResponse,
    TaskOut,
    TaskPatch,
    TaskStatusUpdate,
    TaskUpdate,
)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


def _get_owned_task(task_id: int, user: User, db: Session) -> Task:
    """获取当前用户拥有的任务; 不存在或非本人任务统一返回 404 (避免泄露资源存在性)"""
    task = db.get(Task, task_id)
    if task is None or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("", response_model=TaskListResponse)
def list_tasks(
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    priority: TaskPriority | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分页查询当前用户任务, 支持按状态/优先级筛选"""
    conditions = [Task.user_id == current_user.id]
    if status_filter:
        conditions.append(Task.status == status_filter)
    if priority:
        conditions.append(Task.priority == priority)

    total = db.scalar(select(func.count()).select_from(Task).where(*conditions)) or 0
    rows = (
        db.scalars(
            select(Task)
            .where(*conditions)
            .order_by(Task.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .all()
    )
    return TaskListResponse(
        items=rows, total=total, page=page, size=size, pages=ceil(total / size) if total else 0
    )


@router.post("", response_model=TaskOut, status_code=201)
def create_task(
    payload: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = Task(user_id=current_user.id, **payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_owned_task(task_id, current_user, db)


@router.put("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """全量更新: 未传的可选字段会被重置为默认值"""
    task = _get_owned_task(task_id, current_user, db)
    task.title = payload.title
    task.description = payload.description
    task.priority = payload.priority
    task.due_date = payload.due_date
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}", response_model=TaskOut)
def patch_task(
    task_id: int,
    payload: TaskPatch,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """部分更新: 仅更新显式传入的字段"""
    task = _get_owned_task(task_id, current_user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}/status", response_model=TaskOut)
def change_status(
    task_id: int,
    payload: TaskStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """状态流转业务规则: 已完成(done)为终态, 不允许再变更为其他状态"""
    task = _get_owned_task(task_id, current_user, db)
    if task.status == TaskStatus.DONE and payload.status != TaskStatus.DONE:
        raise HTTPException(
            status_code=409, detail="Completed task is final and cannot change status"
        )
    task.status = payload.status
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_owned_task(task_id, current_user, db)
    db.delete(task)
    db.commit()
