"""配置项管理接口 /api/admin/config（对应图中 api.* / rss.* 可配置项）。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.base import to_dict, to_dicts
from app.models.sys_config import SysConfig
from app.models.user import SysUser
from app.response import ApiException, ok
from app.services.config_service import READONLY_CONFIG_KEYS, clear_cache, get_config
from app.services.crud import get_val
from app.services.log_service import write_log

router = APIRouter(prefix="/admin/config", tags=["配置项"])


@router.get("/list")
def list_configs(db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    rows = db.query(SysConfig).order_by(SysConfig.config_id).all()
    return ok(to_dicts(rows))


@router.get("/value/{key}")
def get_value(key: str, _: SysUser = Depends(get_current_user)):
    return ok({"key": key, "value": get_config(key)})


@router.post("/edit")
def edit_config(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    config_id = get_val(payload, "config_id")
    row = db.get(SysConfig, config_id) if config_id else None
    if not row:
        raise ApiException("记录不存在", 404)
    if row.config_key in READONLY_CONFIG_KEYS:
        raise ApiException(f"{row.config_key} 为系统内置通讯key，不允许修改", 403)
    value = get_val(payload, "config_value", "")
    row.config_value = str(value)
    config_name = get_val(payload, "config_name")
    if config_name is not None:
        row.config_name = config_name
    remark = get_val(payload, "remark")
    if remark is not None:
        row.remark = remark
    db.commit()
    clear_cache()
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="修改配置项", user_name=user.user_name, request_params=payload)
    return ok(msg="修改成功")


@router.post("/batch")
def batch_edit_config(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """批量修改：传入 {config_key: value} 字典。"""
    values = get_val(payload, "values") or payload
    blocked = set(values) & set(READONLY_CONFIG_KEYS)
    if blocked:
        raise ApiException(f"{', '.join(sorted(blocked))} 为系统内置通讯key，不允许修改", 403)
    for key, value in values.items():
        if key in ("values",):
            continue
        row = db.query(SysConfig).filter(SysConfig.config_key == key).first()
        if row:
            row.config_value = str(value)
    db.commit()
    clear_cache()
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="批量修改配置项", user_name=user.user_name, request_params=payload)
    return ok(msg="保存成功")
