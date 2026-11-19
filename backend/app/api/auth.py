"""后台鉴权路由：登录、当前用户、登出、修改密码。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.user import SysUser
from app.response import ApiException, ok
from app.schemas.auth import LoginIn, PasswordChangeIn
from app.services.log_service import write_log
from app.utils.security import (
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["鉴权"])


def _user_info(user: SysUser) -> dict:
    return {
        "userId": user.user_id,
        "userName": user.user_name,
        "nickName": user.nick_name,
        "avatar": "",
    }


@router.post("/login")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    """用户名 + 密码登录，返回 JWT。"""
    user = db.query(SysUser).filter(SysUser.user_name == payload.username).first()
    ip = request.client.host if request.client else None

    if user is None or not verify_password(payload.password, user.password):
        write_log(
            log_type="login",
            method="POST",
            url=str(request.url.path),
            description="登录失败",
            user_name=payload.username,
            ip=ip,
            request_params={"username": payload.username},
            status_code=401,
            success=False,
            error_msg="用户名或密码错误",
        )
        raise ApiException("用户名或密码错误", 401)

    if user.status != "0":
        write_log(
            log_type="login",
            method="POST",
            url=str(request.url.path),
            description="登录失败",
            user_name=payload.username,
            ip=ip,
            success=False,
            error_msg="账号已停用",
        )
        raise ApiException("账号已停用", 403)

    user.login_ip = ip
    user.login_date = datetime.now()
    db.commit()

    token = create_access_token(str(user.user_id), {"user_name": user.user_name})
    write_log(
        log_type="login",
        method="POST",
        url=str(request.url.path),
        description="登录成功",
        user_name=user.user_name,
        ip=ip,
        success=True,
    )
    return ok({"token": token, "userInfo": _user_info(user)})


@router.get("/info")
def info(user: SysUser = Depends(get_current_user)):
    """获取当前登录用户信息。"""
    return ok(_user_info(user))


@router.post("/logout")
def logout(user: SysUser = Depends(get_current_user)):
    """退出登录（JWT 无状态，前端丢弃令牌即可）。"""
    return ok(msg="已退出登录")


@router.post("/password")
def change_password(
    payload: PasswordChangeIn,
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改当前用户密码。"""
    if not verify_password(payload.old_password, user.password):
        raise ApiException("原密码不正确", 400)
    user.password = hash_password(payload.new_password)
    db.commit()
    return ok(msg="密码修改成功")
