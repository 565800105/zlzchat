"""更新记录接口 /api/admin/updateLog。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.base import to_dict, to_dicts
from app.models.feeds import CnvpFeeds
from app.models.update_log import CnvpUpdateLog
from app.models.user import SysUser
from app.response import ApiException, ok, page_result
from app.services.crud import get_val, apply_audit, fill, paginate, parse_ids

router = APIRouter(prefix="/admin/updateLog", tags=["更新记录"])

_FIELDS = ["log_sta", "log_result_sta", "log_catagory", "update_num", "feed_name", "history_start_num", "history_end_num", "is_deleted", "remark"]


@router.get("/list")
def list_logs(
    pageNum: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1),
    feedName: str | None = None,
    logCatagory: str | None = None,
    logSta: str | None = None,
    logResultSta: str | None = None,
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    stmt = select(CnvpUpdateLog).where(CnvpUpdateLog.is_deleted == 0)
    if feedName:
        stmt = stmt.where(CnvpUpdateLog.feed_name.like(f"%{feedName}%"))
    if logCatagory:
        stmt = stmt.where(CnvpUpdateLog.log_catagory == logCatagory)
    if logSta:
        stmt = stmt.where(CnvpUpdateLog.log_sta == logSta)
    if logResultSta:
        stmt = stmt.where(CnvpUpdateLog.log_result_sta == logResultSta)
    stmt = stmt.order_by(CnvpUpdateLog.log_id.desc())
    rows, total = paginate(db, stmt, pageNum, pageSize)
    data = to_dicts(rows)
    # 旧记录 feed_name 可能存的是 wxsId 或为空，按 wxs_id 反查中文名用于展示
    pending = [item for item in data if not item.get("feed_name") or str(item["feed_name"]).startswith("MP_")]
    if pending:
        wxs_ids = {str(item["feed_name"]) for item in pending if item.get("feed_name")}
        name_map = {}
        if wxs_ids:
            for row in db.query(CnvpFeeds).filter(CnvpFeeds.wxs_id.in_(wxs_ids)).all():
                if row.mp_name:
                    name_map[row.wxs_id] = row.mp_name
        for item in pending:
            wxs_id = str(item.get("feed_name") or "")
            item["feed_name"] = name_map.get(wxs_id, wxs_id)
    return page_result(data, total, pageNum, pageSize)


@router.get("/{log_id}")
def get_log(log_id: int, db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    row = db.get(CnvpUpdateLog, log_id)
    if not row:
        raise ApiException("记录不存在", 404)
    return ok(to_dict(row))


@router.post("/add")
def add_log(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    row = CnvpUpdateLog(is_deleted=0)
    fill(row, payload, _FIELDS)
    apply_audit(row, user.user_name, True)
    db.add(row)
    db.commit()
    return ok(msg="新增成功")


@router.post("/edit")
def edit_log(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    row = db.get(CnvpUpdateLog, get_val(payload, "log_id")) if get_val(payload, "log_id") else None
    if not row:
        raise ApiException("记录不存在", 404)
    fill(row, payload, _FIELDS)
    apply_audit(row, user.user_name, False)
    db.commit()
    return ok(msg="修改成功")


@router.post("/remove")
def remove_logs(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    ids = parse_ids(get_val(payload, "ids"))
    if not ids:
        raise ApiException("未选择记录")
    db.query(CnvpUpdateLog).filter(CnvpUpdateLog.log_id.in_(ids)).update(
        {CnvpUpdateLog.is_deleted: 1}, synchronize_session=False
    )
    db.commit()
    return ok(msg="删除成功")
