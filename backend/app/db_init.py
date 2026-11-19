"""数据库初始化：建表 + 默认管理员 + 默认配置项 + 默认定时任务。

供两处复用：
- scripts/init_db.py（手动初始化）
- app/main.py 启动时检测空库自动初始化
"""
from __future__ import annotations

from sqlalchemy import inspect

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import (  # noqa: F401  确保全部模型已注册
    CnvpAccounts,
    CnvpFeeds,
    CnvpMpArticles,
    CnvpMpClassification,
    CnvpMpClassificationDetail,
    CnvpUpdateLog,
    RequestLog,
    TaskDetailLog,
    SysConfig,
    SysJob,
    SysJobLog,
    SysUser,
)
from app.services.config_service import DEFAULT_CONFIGS, CONFIG_REMARKS
from app.utils.security import hash_password

# 用于判断是否空库的关键表
_SENTINEL_TABLE = "sys_user"


def is_empty_database() -> bool:
    """关键表不存在视为空库，需要初始化。"""
    try:
        return _SENTINEL_TABLE not in inspect(engine).get_table_names()
    except Exception:
        return True


def init_database(verbose: bool = True) -> None:
    """建表并写入默认数据（幂等，已有数据不覆盖）。"""
    from pathlib import Path

    def log(msg: str) -> None:
        if verbose:
            print(msg)

    # SQLite 需要确保数据目录存在
    if settings.is_sqlite:
        db_path = settings.DATABASE_URL.split("///", 1)[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(engine)
    log("[OK] 数据库表已创建")

    with SessionLocal() as db:
        # 默认管理员
        if not db.query(SysUser).filter(SysUser.user_name == "admin").first():
            db.add(
                SysUser(
                    user_name="admin",
                    nick_name="超级管理员",
                    password=hash_password("admin123"),
                    status="0",
                    create_by="system",
                )
            )
            log("[OK] 已创建默认管理员 admin / admin123")

        # 默认配置项
        for key, value in DEFAULT_CONFIGS.items():
            if not db.query(SysConfig).filter(SysConfig.config_key == key).first():
                db.add(
                    SysConfig(
                        config_key=key,
                        config_name=key,
                        config_value=value,
                        config_type="N",
                        create_by="system",
                        remark=CONFIG_REMARKS.get(key, ""),
                    )
                )
        log("[OK] 默认配置项已就绪")

        # 默认定时任务
        if not db.query(SysJob).first():
            db.add(
                SysJob(
                    job_name="定时拉取微信文章",
                    cron_expression="0 0 8 * * ?",
                    misfire_policy="3",
                    concurrent="1",
                    status="0",
                    acount_type="2",
                    classification_id=[],
                    wxs_id=[],
                    remark="每天 08:00 拉取文章",
                    create_by="system",
                )
            )
            log("[OK] 默认定时任务已就绪（默认开启）")

        db.commit()
    log("[DONE] 初始化完成")
