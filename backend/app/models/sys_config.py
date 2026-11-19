"""系统配置模型（对应 sys_config），用于存放 api.* / rss.* 等可配置项。"""
from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class SysConfig(Base, AuditMixin):
    __tablename__ = "sys_config"
    __table_args__ = {"comment": "参数配置表"}

    config_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="参数主键")
    config_name: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="参数名称")
    config_key: Mapped[str] = mapped_column(String(100), unique=True, index=True, comment="参数键名")
    config_value: Mapped[str | None] = mapped_column(String(2000), nullable=True, default="", comment="参数键值")
    config_type: Mapped[str] = mapped_column(String(1), default="N", comment="是否内置 Y是 N否")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
