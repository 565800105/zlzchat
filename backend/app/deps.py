"""FastAPI 依赖注入：当前登录管理员。"""
from __future__ import annotations

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import SysUser
from app.response import ApiException
from app.utils.security import decode_access_token


def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> SysUser:
    """从 Authorization: Bearer <token> 解析出当前用户。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiException("未登录或令牌无效", 401)
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub", ""))
    except Exception:
        raise ApiException("登录已过期，请重新登录", 401)

    user = db.get(SysUser, user_id)
    if user is None or user.status != "0":
        raise ApiException("账号不存在或已停用", 401)

    # 挂到 request.state 供日志中间件读取
    request.state.user_name = user.user_name
    return user


# 依赖别名，便于在路由中书写
CurrentUser = Depends(get_current_user)
