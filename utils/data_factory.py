"""测试数据工厂: 基于 Faker 生成随机唯一测试数据

随机数据保证用例间数据隔离与可重复执行 (幂等回归);
特殊构造数据 (边界值/异常值) 则沉淀在 testdata/ 下供数据驱动用例使用。
"""
import random
import string
import time

from faker import Faker

fake = Faker("zh_CN")
_seq = 0


def unique_username(prefix: str = "tester") -> str:
    """生成全局唯一用户名 (3-20位字母数字下划线)"""
    global _seq
    _seq += 1
    return f"{prefix}_{int(time.time() * 1000) % 10_000_000}_{_seq}"[:20]


def random_password(min_len: int = 8, max_len: int = 16) -> str:
    """生成随机密码"""
    return fake.password(length=random.randint(min_len, max_len))


def random_task_title() -> str:
    """生成随机任务标题 (<=100字符)"""
    return fake.sentence(nb_words=4)[:100]


def random_task(overrides: dict | None = None) -> dict:
    """生成一条合法的任务请求体"""
    payload = {
        "title": random_task_title(),
        "description": fake.sentence(nb_words=10),
        "priority": random.choice(["low", "medium", "high"]),
        "due_date": fake.date_between(start_date="+1d", end_date="+30d").isoformat(),
    }
    if overrides:
        payload.update(overrides)
    return payload


def boundary_title(length: int) -> str:
    """生成指定长度的任务标题 (用于边界值用例)"""
    return "".join(random.choices(string.ascii_letters, k=length))
