"""账号配置接口 /api/admin/accounts。"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.accounts import CnvpAccounts
from app.models.user import SysUser
from app.response import ApiException, ok, page_result
from app.services.crud import get_val, apply_audit, fill, paginate, parse_ids
from app.services.log_service import write_log

router = APIRouter(prefix="/admin/accounts", tags=["账号配置"])

_FIELDS = ["cookie_value", "nick_name", "status", "category", "is_deleted", "remark"]


@router.get("/list")
def list_accounts(
    pageNum: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1),
    status: int | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    from sqlalchemy import select

    stmt = select(CnvpAccounts).where(CnvpAccounts.is_deleted == 0)
    if status is not None:
        stmt = stmt.where(CnvpAccounts.status == status)
    if category:
        stmt = stmt.where(CnvpAccounts.category == category)
    stmt = stmt.order_by(CnvpAccounts.create_time.desc())
    rows, total = paginate(db, stmt, pageNum, pageSize)
    from app.models.base import to_dicts

    return page_result(to_dicts(rows), total, pageNum, pageSize)


@router.post("/add")
def add_account(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    row = CnvpAccounts(accounts_id=get_val(payload, "accounts_id") or uuid.uuid4().hex, status=1, is_deleted=0)
    fill(row, payload, _FIELDS)
    apply_audit(row, user.user_name, is_new=True)
    db.add(row)
    db.commit()
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="新增账号", user_name=user.user_name, request_params=payload, success=True)
    return ok(msg="新增成功")


@router.post("/edit")
def edit_account(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    accounts_id = get_val(payload, "accounts_id")
    if not accounts_id:
        raise ApiException("缺少 accounts_id")
    row = db.get(CnvpAccounts, accounts_id)
    if not row:
        raise ApiException("记录不存在", 404)
    fill(row, payload, _FIELDS)
    apply_audit(row, user.user_name, is_new=False)
    db.commit()
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="编辑账号", user_name=user.user_name, request_params=payload, success=True)
    return ok(msg="修改成功")


@router.post("/remove")
def remove_accounts(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    ids = parse_ids(get_val(payload, "ids"))
    if not ids:
        raise ApiException("未选择记录")
    db.query(CnvpAccounts).filter(CnvpAccounts.accounts_id.in_(ids)).update(
        {CnvpAccounts.is_deleted: 1}, synchronize_session=False
    )
    db.commit()
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="删除账号", user_name=user.user_name, request_params=payload, success=True)
    return ok(msg="删除成功")


# ---------- 微信读书扫码登录 ----------
def _external_get(path: str, params: dict | None = None, no_time: bool = False) -> dict:
    """调用外部扫码服务（对应 Java ApiCommon.getApi / getApiNoTime）。"""
    import httpx

    from app.services.config_service import get_api_server_url

    # 中转服务请求不再携带 token（兑换券配置已取消）
    url = f"{get_api_server_url()}{path}"
    timeout = 300 if no_time else 30
    try:
        resp = httpx.get(url, params=params, timeout=timeout)
        try:
            result = resp.json()
        except Exception:
            raise ApiException(
                f"扫码服务返回异常(HTTP {resp.status_code}): {resp.text[:200]}。请检查配置项 api.serverUrl 是否正确。", 500
            )
        code = str(result.get("code", ""))
        msg = str(result.get("msg", ""))
        return result
    except ApiException:
        raise
    except Exception as exc:
        raise ApiException(f"扫码服务请求失败（请检查配置项 api.serverUrl 登录态续期服务地址）: {exc}", 500)


@router.get("/qrcode")
def get_qrcode(_: SysUser = Depends(get_current_user)):
    """获取微信读书登录二维码（对应 Java /ewm）。"""
    result = _external_get("/getEwm")
    if str(result.get("code")) != "0":
        raise ApiException(result.get("msg") or "获取二维码失败", 500)
    data = result.get("data") or {}
    return ok({"url": data.get("url"), "uid": data.get("uid"), "installId": data.get("installId")})


@router.get("/qrcode/check")
def check_qrcode(
    uid: str,
    installId: str,
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """轮询扫码结果，成功后自动创建微信账号并刷新登录态（对应 Java /ewmCallback）。

    始终返回 HTTP 200，用 data.success 明确告知前端是否已扫码成功：
    - success=false：尚未扫码/服务暂未返回凭证，前端应继续轮询（不弹错误）
    - success=true ：已拿到有效凭证并完成入库，前端应停止轮询并刷新列表
    """
    try:
        result = _external_get("/ewmCallback", {"uid": uid, "installId": installId}, no_time=True)
    except ApiException:
        # 外部服务不可用时也返回"未完成"，交由前端超时机制处理，避免反复弹错误
        return ok({"success": False, "message": "等待扫码"})

    if str(result.get("code")) != "0":
        return ok({"success": False, "message": result.get("msg") or "等待扫码"})

    data = result.get("data") or {}
    cookie_value = data.get("token") or ""
    # 关键：必须拿到有效凭证才算扫码成功，避免误判导致轮询提前停止或一直转圈
    if not cookie_value:
        return ok({"success": False, "message": "等待扫码"})

    nick_name = data.get("nickName") or "微信读书用户"

    # 幂等：已存在则直接返回成功，不重复入库
    existing = db.query(CnvpAccounts).filter(
        CnvpAccounts.cookie_value == cookie_value, CnvpAccounts.is_deleted == 0
    ).first()
    if not existing:
        row = CnvpAccounts(
            accounts_id=uuid.uuid4().hex,
            category="1",
            nick_name=nick_name,
            cookie_value=cookie_value,
            status=1,
            is_deleted=0,
        )
        apply_audit(row, user.user_name, is_new=True)
        db.add(row)
        db.commit()
        # 扫码后立即刷新登录态（不节流）
        from app.services.wxread import WxReadService

        try:
            WxReadService(db).refresh_skey_no_time(row)
        except Exception:
            pass  # 刷新失败不阻断扫码成功

    write_log(
        log_type="operation", method="GET", url=str(request.url.path),
        description="微信扫码新增账号", user_name=user.user_name,
        request_params={"uid": uid, "nickName": nick_name}, success=True,
    )
    return ok({"success": True, "nickName": nick_name})


@router.get("/{accounts_id}")
def get_account(accounts_id: str, db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    row = db.get(CnvpAccounts, accounts_id)
    if not row:
        raise ApiException("记录不存在", 404)
    from app.models.base import to_dict

    return ok(to_dict(row))
