"""统一日志管理 (loguru): 控制台 + 按天滚动的文件双输出"""
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

_initialized = False


def setup_logger(log_dir: Path, level: str = "INFO") -> None:
    """初始化全局日志器, 幂等 (重复调用不叠加 handler)"""
    global _initialized
    if _initialized:
        return
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"test-{datetime.now():%Y%m%d}.log"

    logger.remove()
    logger.add(sys.stdout, level=level, format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}")
    logger.add(log_file, level="DEBUG", rotation="10 MB", retention="7 days", encoding="utf-8",
               format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <7} | {name}:{line} | {message}")
    _initialized = True
    logger.info(f"日志文件: {log_file}")
