"""文章信息接口 /api/admin/mparticles。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.articles import CnvpMpArticles
from app.models.base import to_dict, to_dicts
from app.models.feeds import CnvpFeeds
from app.models.user import SysUser
from app.response import ApiException, ok, page_result
from app.services.crud import get_val, apply_audit, fill, paginate, parse_ids
from app.services.log_service import write_log
from app.services.wxread import WxReadService

router = APIRouter(prefix="/admin/mparticles", tags=["文章信息"])

_FIELDS = ["original_id", "wxs_id", "title", "links", "doc_url", "pic_url", "publish_time", "content", "content_text", "read_type", "is_deleted", "remark"]


@router.get("/list")
def list_articles(
    pageNum: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1),
    title: str | None = None,
    wxsId: str | None = None,
    readType: str | None = None,
    beginTime: str | None = None,
    endTime: str | None = None,
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    sub = select(CnvpFeeds.wxs_id, CnvpFeeds.mp_name, CnvpFeeds.mp_cover).subquery()
    stmt = (
        select(CnvpMpArticles, sub.c.mp_name, sub.c.mp_cover)
        .outerjoin(sub, CnvpMpArticles.wxs_id == sub.c.wxs_id)
        .where(CnvpMpArticles.is_deleted == 0, or_(sub.c.mp_name.is_(None), sub.c.mp_name != ""))
    )
    if title:
        stmt = stmt.where(CnvpMpArticles.title.like(f"%{title}%"))
    if wxsId:
        stmt = stmt.where(CnvpMpArticles.wxs_id == wxsId)
    if readType:
        stmt = stmt.where(CnvpMpArticles.read_type == readType)
    if beginTime:
        stmt = stmt.where(CnvpMpArticles.publish_time >= beginTime)
    if endTime:
        stmt = stmt.where(CnvpMpArticles.publish_time <= endTime)
    stmt = stmt.order_by(CnvpMpArticles.publish_time.desc())

    total = db.query(stmt.subquery()).count()
    rows = db.execute(stmt.offset((pageNum - 1) * pageSize).limit(pageSize)).all()
    data = []
    for row, mp_name, mp_cover in rows:
        item = to_dict(row)
        item["mpName"] = mp_name or ""
        item["mp_name"] = mp_name or ""  # 兼容前端下划线命名
        item["mpCover"] = mp_cover or ""
        item["mp_cover"] = mp_cover or ""
        item["content"] = ""  # 列表不返回正文，减小体积
        item.pop("imgUrl", None)
        data.append(item)
    return page_result(data, total, pageNum, pageSize)


@router.get("/{articles_id}")
def get_article(articles_id: str, db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    row = db.get(CnvpMpArticles, articles_id)
    if not row:
        raise ApiException("记录不存在", 404)
    data = to_dict(row)
    # 联表带出公众号名称/封面（文章表本身不含 mp_name，详情弹窗需要展示）
    feed = (
        db.query(CnvpFeeds)
        .filter(CnvpFeeds.wxs_id == row.wxs_id, CnvpFeeds.is_deleted == 0)
        .first()
    )
    data["mp_name"] = feed.mp_name if feed and feed.mp_name else ""
    data["mp_cover"] = feed.mp_cover if feed and feed.mp_cover else ""
    return ok(data)


@router.post("/add")
def add_article(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    row = CnvpMpArticles(articles_id=uuid.uuid4().hex, original_id="", wxs_id="", is_deleted=0)
    fill(row, payload, _FIELDS)
    apply_audit(row, user.user_name, True)
    db.add(row)
    db.commit()
    return ok(msg="新增成功")


@router.post("/edit")
def edit_article(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    row = db.get(CnvpMpArticles, get_val(payload, "articles_id")) if get_val(payload, "articles_id") else None
    if not row:
        raise ApiException("记录不存在", 404)
    fill(row, payload, _FIELDS)
    apply_audit(row, user.user_name, False)
    db.commit()
    return ok(msg="修改成功")


@router.post("/remove")
def remove_articles(
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    ids = parse_ids(get_val(payload, "ids"))
    if not ids:
        raise ApiException("未选择记录")
    db.query(CnvpMpArticles).filter(CnvpMpArticles.articles_id.in_(ids)).update(
        {CnvpMpArticles.is_deleted: 1}, synchronize_session=False
    )
    db.commit()
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="删除文章", user_name=user.user_name, request_params=payload)
    return ok(msg="删除成功")


@router.post("/goCont/{articles_id}")
def go_content(
    articles_id: str,
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """重新抓取文章正文。"""
    row = db.get(CnvpMpArticles, articles_id)
    if not row:
        raise ApiException("记录不存在", 404)
    service = WxReadService(db)
    content, content_text = service.fetch_content(row.doc_url or row.links or "")
    row.content = content
    row.content_text = content_text
    db.commit()
    return ok(msg="抓取完成")


@router.post("/getFeedArticleNew/{wxs_id}")
def sync_latest(
    wxs_id: str,
    request: Request,
    taskId: str | None = None,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """同步指定公众号的最新文章。taskId 用于前端刷新后查询任务结果。"""
    from app.services.task_status import finish_task, start_task

    if taskId:
        start_task(taskId)
    result = WxReadService(db).sync_latest(wxs_id)
    code = result.get("code")
    update_num = ((result.get("data") or {}).get("updateNum", 0)) if code == 200 else 0
    if taskId:
        finish_task(
            taskId,
            status="success" if code == 200 else "error",
            msg=result.get("msg") or "",
            update_num=update_num,
        )
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="同步最新文章", user_name=user.user_name, request_params={"wxsId": wxs_id}, success=code == 200, error_msg=None if code == 200 else result.get("msg"))
    return result


@router.post("/getFeedArticle/{wxs_id}")
def sync_history(
    wxs_id: str,
    payload: dict[str, Any] | None = None,
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """同步指定公众号的历史文章（对应 Java getFeedArticle）。payload 可含 taskId。"""
    from app.services.task_status import finish_task, start_task

    payload = payload or {}
    task_id = get_val(payload, "taskId")
    if task_id:
        start_task(task_id)
    result = WxReadService(db).sync_history(
        wxs_id,
        his_type=get_val(payload, "hisType", 1),
        start=int(get_val(payload, "startNum", 0) or 0),
        end=int(get_val(payload, "endNum", 0) or 0),
    )
    code = result.get("code")
    update_num = ((result.get("data") or {}).get("updateNum", 0)) if code == 200 else 0
    if task_id:
        finish_task(
            task_id,
            status="success" if code == 200 else "error",
            msg=result.get("msg") or "",
            update_num=update_num,
        )
    return result


@router.get("/taskStatus/{task_id}")
def task_status(task_id: str, _: SysUser = Depends(get_current_user)):
    """前端刷新后凭 taskId 查询后台任务真实状态。"""
    from app.services.task_status import get_task

    task = get_task(task_id)
    if not task:
        return ok(None)
    return ok(task)


@router.post("/deleteFeedArticle/{wxs_id}")
def delete_feed_articles(
    wxs_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """物理删除指定公众号的全部文章并重置 update_count。"""
    deleted = db.query(CnvpMpArticles).filter(CnvpMpArticles.wxs_id == wxs_id).delete(synchronize_session=False)
    feed = db.query(CnvpFeeds).filter(CnvpFeeds.wxs_id == wxs_id, CnvpFeeds.is_deleted == 0).first()
    if feed:
        feed.update_count = 0
    db.commit()
    write_log(log_type="operation", method="POST", url=str(request.url.path), description="清空公众号文章", user_name=user.user_name, request_params={"wxsId": wxs_id})
    return ok(deleted)
