"""配置服务：读取/写入 sys_config 中的 api.* / rss.* 等可配置项，带轻量缓存。"""
from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.sys_config import SysConfig

# 与 Java update.sql / grwxgzh.sql 中的默认值保持一致
DEFAULT_CONFIGS: dict[str, str] = {
    "api.articlecont": "1",
    "api.dingdingToken": "",
    "api.dingdingSecret": "",
    "api.apiKey": "",
    "api.feishuUrl": "",
    "api.feishuSecret": "",
    "api.updateFeedTime": "60",
    "api.checkFeedUpdate": "1",
    # 外部中转服务地址，扫码/刷新登录态均走此地址
    "api.serverUrl": "http://111.229.83.152",
    "rss.name": "我的订阅",
    "rss.count": "50",
    # 服务器对外域名/IP：订阅源(OPML/RSS/Atom)中图片等资源地址的拼接前缀
    "api.publicUrl": "",
    # 中转服务通讯key：用于解析账号 cookie(JWT) 中的 loginInfo，与中转服务约定一致
    "api.middlewareKey": "MSKEY@!sYSA 2025-04-22 08:30:00",
}

# 只读配置项：不允许在配置页修改（后端也会拦截），前端据此禁用编辑
READONLY_CONFIG_KEYS = ("api.middlewareKey",)

# 配置说明（写入 sys_config.remark，供配置项管理页"说明"列展示）
CONFIG_REMARKS: dict[str, str] = {
    "api.apiKey": "服务提供api鉴权key",
    "api.serverUrl": "登录态续期服务地址",
    "api.publicUrl": "服务器对外域名/IP，用于订阅源中图片等资源地址",
    "api.middlewareKey": "中转服务通讯key，系统内置，不允许修改",
}

_CACHE_TTL = 5.0
_cache: dict[str, tuple[str, float]] = {}


def get_config(key: str, default: str = "", db: Session | None = None) -> str:
    """读取配置值，未命中缓存则查库。"""
    now = time.time()
    cached = _cache.get(key)
    if cached and now - cached[1] < _CACHE_TTL:
        return cached[0]

    own = db is None
    session = db or SessionLocal()
    try:
        row = session.query(SysConfig).filter(SysConfig.config_key == key).first()
        value = row.config_value if row and row.config_value is not None else None
        # 库中为空时回退到内置默认值
        if not value:
            value = DEFAULT_CONFIGS.get(key, default)
        _cache[key] = (value, now)
        return value
    finally:
        if own:
            session.close()


def get_api_server_url() -> str:
    """外部中转服务地址：优先取配置项 api.serverUrl，回退环境变量默认值。

    扫码(getEwm/ewmCallback)与刷新登录态
    (refSkeyAPP/refSkeyAPPNoTime)均使用此地址。
    """
    from app.config import settings

    value = (get_config("api.serverUrl") or "").strip().rstrip("/")
    return value or settings.API_SERVER_URL.rstrip("/")


def get_public_url() -> str:
    """服务器对外域名/IP（已去尾斜杠），用于订阅源里图片等资源地址拼接。

    未配置时返回空字符串，调用方应回退到相对路径或请求来源地址。
    """
    return (get_config("api.publicUrl") or "").strip().rstrip("/")


def absolute_resource_url(url: str | None, public_url: str | None = None) -> str:
    """把资源地址补全为对外可访问的绝对地址。

    - http(s)/协议相对(//)/data: 原样返回
    - 相对路径(/开头) 拼上 public_url；无 public_url 时原样返回
    """
    if not url:
        return ""
    value = str(url).strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://", "//", "data:")):
        return value
    base = (public_url if public_url is not None else get_public_url()).rstrip("/")
    if not base:
        return value
    if not value.startswith("/"):
        value = "/" + value
    return f"{base}{value}"


# 已废弃、不再使用的配置项（启动时从库中清理，避免出现在配置项页）
# api.token：兑换券已去掉，请求头 token 固定传空值
OBSOLETE_CONFIG_KEYS = ("resource.downloadurl", "wxsSynchronous", "api.token")


def ensure_default_configs() -> None:
    """把内置默认配置补进库（幂等），确保已有数据库也能在配置项页看到完整列表。

    仅新增缺失的键，不覆盖用户已修改的值；同时清理已废弃的配置项。
    """
    session = SessionLocal()
    try:
        from app.models.sys_config import SysConfig

        existing = {
            row[0]
            for row in session.query(SysConfig.config_key).all()
        }
        added = False
        for key, value in DEFAULT_CONFIGS.items():
            if key not in existing:
                session.add(
                    SysConfig(
                        config_key=key,
                        config_name=key,
                        config_value=value,
                        config_type="N",
                        remark=CONFIG_REMARKS.get(key, ""),
                    )
                )
                added = True
        # 只读配置项：即使历史库中值被改过，也强制同步回内置值
        for key in READONLY_CONFIG_KEYS:
            row = session.query(SysConfig).filter(SysConfig.config_key == key).first()
            if row and row.config_value != DEFAULT_CONFIGS[key]:
                row.config_value = DEFAULT_CONFIGS[key]
                added = True
        # 配置说明：把说明同步到 remark（兼容历史库 remark 为空）
        for key, remark in CONFIG_REMARKS.items():
            row = session.query(SysConfig).filter(SysConfig.config_key == key).first()
            if row and row.remark != remark:
                row.remark = remark
                added = True
        # 清理废弃配置项
        removed = (
            session.query(SysConfig)
            .filter(SysConfig.config_key.in_(OBSOLETE_CONFIG_KEYS))
            .delete(synchronize_session=False)
        )
        if added or removed:
            session.commit()
            clear_cache()
    finally:
        session.close()


def get_config_int(key: str, default: int = 0) -> int:
    try:
        return int(get_config(key, str(default)))
    except (ValueError, TypeError):
        return default


def get_config_bool(key: str, default: bool = False) -> bool:
    return get_config(key, "1" if default else "0") == "1"


def set_config(key: str, value: str, db: Session | None = None) -> None:
    """写入配置值并刷新缓存。"""
    own = db is None
    session = db or SessionLocal()
    try:
        row = session.query(SysConfig).filter(SysConfig.config_key == key).first()
        if row:
            row.config_value = value
        else:
            session.add(
                SysConfig(
                    config_key=key,
                    config_name=key,
                    config_value=value,
                    config_type="N",
                )
            )
        session.commit()
        _cache[key] = (value, time.time())
    finally:
        if own:
            session.close()


def clear_cache() -> None:
    _cache.clear()
