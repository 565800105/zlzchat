"""全局配置：所有可调参数集中在此，支持 .env 覆盖。"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# backend 目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 加载 .env（若存在）
load_dotenv(BASE_DIR / ".env")

# 数据目录：图片资源、SQLite 库、迁移图片目标目录都放这里。
# Docker 部署时可设为挂载卷路径（如 /app/data），宿主机挂载即可持久化。
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()


class Settings:
    """应用配置，全部可通过环境变量覆盖。"""

    APP_NAME: str = os.getenv("APP_NAME", "ZLZCHAT 公众号信息管理系统")
    API_PREFIX: str = "/api"

    # 鉴权
    SECRET_KEY: str = os.getenv("SECRET_KEY", "zlzchat-secret-key-change-me")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
    )

    # 数据库：默认 SQLite，落库到 backend/data/zlzchat.db
    _db = os.getenv("DATABASE_URL", "").strip()
    DATABASE_URL: str = _db or f"sqlite:///{DATA_DIR.joinpath('zlzchat.db').as_posix()}"

    # 微信读书外部服务（skey 刷新 / 正文下载 jar 服务）
    API_SERVER_URL: str = os.getenv(
        "API_SERVER_URL", "http://111.229.83.152"
    ).rstrip("/")

    # 服务监听
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8100"))

    # 日志：后台"只看最新"策略保留的条数
    LOG_KEEP_RECENT: int = int(os.getenv("LOG_KEEP_RECENT", "100"))

    # 任务明细日志保留条数（按需调大以保留更长的回溯历史）
    LOG_DETAIL_KEEP: int = int(os.getenv("LOG_DETAIL_KEEP", "2000"))

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


settings = Settings()
