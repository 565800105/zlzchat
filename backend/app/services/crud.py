"""通用 CRUD 辅助：分页、ID 解析、审计字段填充。"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlalchemy import Select
from sqlalchemy.orm import Session

from app.models.base import Base, AuditMixin


def _camel_to_snake(name: str) -> str:
    """mpName -> mp_name（用于兼容前端驼峰字段）。"""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _snake_to_camel(name: str) -> str:
    """mp_name -> mpName。"""
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def get_val(data: dict[str, Any], key: str, default: Any = None) -> Any:
    """按 key 取值，同时兼容驼峰/下划线两种命名（无痕对接前端与 Java 数据）。"""
    if key in data:
        return data[key]
    camel = _snake_to_camel(key)
    if camel in data:
        return data[camel]
    snake = _camel_to_snake(key)
    if snake in data:
        return data[snake]
    return default


def paginate(db: Session, stmt: Select, page_num: int, page_size: int) -> tuple[list, int]:
    """执行分页查询，返回 (当前页记录, 总数)。"""
    page_num = max(page_num, 1)
    page_size = max(min(page_size, 200), 1)
    total = db.query(stmt.subquery()).count()
    rows = db.scalars(stmt.offset((page_num - 1) * page_size).limit(page_size)).all()
    return list(rows), total


def parse_ids(value: Any) -> list[str]:
    """把 '1,2,3' 或 [1,2,3] 统一转成字符串列表。"""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def fill(obj: Base, data: dict[str, Any], fields: list[str]) -> Base:
    """按字段白名单把字典写入 ORM 对象，兼容驼峰/下划线命名。"""
    for field in fields:
        value = get_val(data, field)
        if value is not None:
            setattr(obj, field, value)
    return obj


def apply_audit(obj: Base, user_name: str, is_new: bool) -> None:
    """填充审计字段，对齐 Java MyMetaObjectHandler 的行为。"""
    now = datetime.now()
    if isinstance(obj, AuditMixin):
        if is_new:
            obj.create_by = user_name
            obj.create_time = now
        obj.update_by = user_name
        obj.update_time = now
