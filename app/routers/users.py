"""用户模块: 注册 / 登录 / 当前用户信息"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token, decode_access_token, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas import TokenResponse, UserLogin, UserOut, UserRegister

router = APIRouter(prefix="/api/v1", tags=["users"])

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """解析 Bearer Token 并返回当前用户; 未认证统一返回 401"""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """用户注册; 用户名重复返回 409"""
    exists = db.scalar(select(User).where(User.username == payload.username))
    if exists:
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """登录成功返回 JWT; 用户名不存在或密码错误均返回 401"""
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/users/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)):
    """返回当前登录用户信息"""
    return current_user
