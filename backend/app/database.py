"""SQLAlchemy 引擎、会话与基类。"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.base import Base  # 全项目唯一声明式基类，确保 create_all 能发现所有表

_connect_args = (
    {"check_same_thread": False} if settings.is_sqlite else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求获取一个独立数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
