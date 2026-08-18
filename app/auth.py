"""密码哈希 (PBKDF2) 与 JWT 签发/校验"""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from app.config import config

_PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    """PBKDF2-SHA256 加盐哈希, 存储格式: salt_hex$hash_hex"""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, hash_hex = stored.split("$")
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), _PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(digest.hex(), hash_hex)


def create_access_token(user_id: int) -> str:
    """签发 JWT, payload 携带 user_id 与过期时间"""
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=config.TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """校验 JWT 并返回 user_id; 无效/过期返回 None"""
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
