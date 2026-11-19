"""ORM 通用基类与序列化工具。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """声明式基类。"""

    pass


class AuditMixin:
    """审计字段混入：与 Java BaseEntity 的 create_by/create_time/update_by/update_time 对齐。"""

    create_by: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="创建者")
    create_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="创建时间")
    update_by: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="更新者")
    update_time: Mapped[datetime | None] = mapped_column(nullable=True, comment="更新时间")


def _convert(value: Any) -> Any:
    if isinstance(value, datetime):
        # 统一为 yyyy-MM-dd HH:mm:ss（去掉微秒），页面展示格式一致
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return value


def _snake_to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def to_dict(obj: Base | None, exclude: set[str] | None = None) -> dict[str, Any]:
    """把 ORM 对象转为普通字典，日期统一转字符串。

    同时输出「属性名 / 列名 / 驼峰名」三套 key，兼容前端驼峰命名与常见字段命名，
    保证无痕迁移：前端用 mp_name 或 mpName 均可取到值。
    """
    if obj is None:
        return {}
    from sqlalchemy import inspect as sa_inspect

    exclude = exclude or set()
    result: dict[str, Any] = {}
    for prop in sa_inspect(obj).mapper.column_attrs:
        attr = prop.key
        column = prop.columns[0].name
        if attr in exclude or column in exclude:
            continue
        value = _convert(getattr(obj, attr, None))
        result[attr] = value
        result[column] = value
        camel = _snake_to_camel(attr)
        if camel != attr:
            result[camel] = value
    return result


def to_dicts(objs: list[Base], exclude: set[str] | None = None) -> list[dict[str, Any]]:
    """批量序列化。"""
    return [to_dict(obj, exclude) for obj in objs]
