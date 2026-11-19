"""微信读书文章拉取核心服务（移植自 Java WxReadCommon）。

完整保留：账号 skey 刷新、book/readinfo 版本检测、book/articles 文章拉取、
正文抓取、封面下载、去重入库、账号轮询/异常切换策略、飞书钉钉通知、同步状态复位。
"""
from __future__ import annotations

import html as html_lib
import json
import logging
import random
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import jwt
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import BASE_DIR, DATA_DIR, settings
from app.models.accounts import CnvpAccounts
from app.models.articles import CnvpMpArticles
from app.models.classification import CnvpMpClassificationDetail
from app.models.feeds import CnvpFeeds
from app.models.sys_config import SysConfig
from app.models.sys_job import SysJob
from app.models.update_log import CnvpUpdateLog
from app.services import notify
from app.services.config_service import (
    get_api_server_url,
    get_config,
    get_config_int,
)
from app.services.log_service import write_log

logger = logging.getLogger(__name__)

_UA = "WeRead/9.3.1 WRBrand/vivo Dalvik/2.1.0 (Linux; U; Android 14; V2171A Build/UP1A.231005.007)"
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_UPLOAD_DIR = DATA_DIR / "uploadGZHFile"

_client = httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": _BROWSER_UA})

# 断点续传内存进度（key -> 已处理到的下标），替代原 Redis 的 updateFeedList/updateFeedNum
_progress: dict[str, int] = {}


class AccountError(RuntimeError):
    """账号被风控/鉴权失败等需要切换账号的异常。"""

    def __init__(self, message: str, code: str = ""):
        self.code = code
        super().__init__(message)


class WxReadService:
    def __init__(self, db: Session):
        self.db = db
        # 任务明细日志上下文：主流程开始时设置，底层步骤自动归属到同一批次
        self._batch: str | None = None
        self._batch_ctx: dict = {}

    # ---------- 任务明细日志埋点 ----------
    def _begin_detail(
        self,
        task_type: str,
        *,
        job_id: int | None = None,
        job_name: str = "",
        wxs_id: str = "",
        feed_name: str = "",
        message: str = "",
    ) -> str:
        """开启一批明细日志，返回 batch_id。"""
        from app.services.task_detail_log_service import new_batch, write_detail

        self._batch = new_batch()
        self._batch_ctx = {
            "task_type": task_type,
            "job_id": job_id,
            "job_name": job_name,
            "wxs_id": wxs_id,
            "feed_name": feed_name,
        }
        write_detail(
            batch_id=self._batch,
            task_type=task_type,
            job_id=job_id,
            job_name=job_name,
            wxs_id=wxs_id,
            feed_name=feed_name,
            step="task_start",
            message=message or f"{job_name or task_type} 开始执行",
        )
        return self._batch

    def _detail(
        self,
        step: str,
        message: str,
        *,
        level: str = "info",
        success: bool = True,
        error_msg: Any = None,
        wxs_id: str | None = None,
        feed_name: str | None = None,
    ) -> None:
        """写入一步明细（仅当处于某批次上下文中，避免影响非任务流程）。"""
        if not self._batch:
            return
        from app.services.task_detail_log_service import write_detail

        ctx = self._batch_ctx
        write_detail(
            batch_id=self._batch,
            task_type=ctx.get("task_type", "job"),
            job_id=ctx.get("job_id"),
            job_name=ctx.get("job_name", ""),
            wxs_id=wxs_id if wxs_id is not None else ctx.get("wxs_id", ""),
            feed_name=feed_name if feed_name is not None else ctx.get("feed_name", ""),
            step=step,
            message=message,
            level=level,
            success=success,
            error_msg=error_msg,
        )

    def _end_detail(
        self, message: str, *, success: bool = True, error_msg: Any = None
    ) -> None:
        self._detail("task_end", message, success=success, error_msg=error_msg)
        self._batch = None
        self._batch_ctx = {}

    # ---------- 账号相关 ----------
    @staticmethod
    def _fastjson_date(value) -> int | None:
        """模拟 fastjson 对 java.util.Date 的序列化：毫秒时间戳数字。

        Java 老代码用 JSONObject.toJSONString(accounts) 传给 /refSkeyAPP，
        其中 createTime/updateTime 是 Date，fastjson 默认输出毫秒时间戳。
        外部服务按 Long.parseLong 解析，若传 ISO 日期字符串会报
        "For input string: 2026-xx-xx ..."。
        """
        if not value:
            return None
        if isinstance(value, datetime):
            return int(value.timestamp() * 1000)
        return None

    @staticmethod
    def _account_payload(account: CnvpAccounts) -> dict:
        """按 Java Bean 驼峰字段序列化账号，供外部 API 刷新登录态。"""
        return {
            "accountsId": account.accounts_id,
            "cookieValue": account.cookie_value,
            "nickName": account.nick_name,
            "status": account.status,
            "category": account.category,
            "createBy": account.create_by,
            "createTime": WxReadService._fastjson_date(account.create_time),
            "updateBy": account.update_by,
            "updateTime": WxReadService._fastjson_date(account.update_time),
            "isDeleted": account.is_deleted,
            "remark": account.remark,
        }

    def refresh_skey(self, account: CnvpAccounts) -> None:
        """刷新账号登录态（距上次刷新 >=55 秒才刷新），失败自动重试并禁用账号。"""
        now = datetime.now()
        if account.update_time and (now - account.update_time).total_seconds() < 55:
            return
        self._detail(
            "verify_login",
            f"验证登录态：账号 {account.nick_name or account.accounts_id}",
        )
        # 中转服务请求不再携带 token（兑换券配置已取消）
        url = f"{get_api_server_url()}/refSkeyAPP"
        attempt = 0          # 异常失败重试次数
        renew_wait = 0       # 「账号正在续期」等待次数（不占用失败重试）
        max_retries = 5
        max_renew_wait = 20  # 最多等 20 次 * 30 秒 = 10 分钟，避免死循环
        while attempt < max_retries:
            try:
                resp = httpx.post(
                    url,
                    json=self._account_payload(account),
                    timeout=30,
                )
                # 账号正在续期：等 30 秒后重新请求，不计入失败重试
                if "该账号正在进行续期" in (resp.text or ""):
                    renew_wait += 1
                    if renew_wait > max_renew_wait:
                        raise AccountError(f"账号续期等待超时: {account.nick_name}")
                    logger.info(
                        "账号正在续期，%d秒后重新请求(第%d次): %s",
                        30, renew_wait, account.nick_name,
                    )
                    time.sleep(30)
                    continue
                data = resp.json()
                if str(data.get("code")) == "0":
                    account.cookie_value = data.get("data")
                    account.update_time = datetime.now()
                    self.db.commit()
                    time.sleep(10)
                    return
                account.status = 2
                self.db.commit()
                msg = f"{account.nick_name}，账号异常，已禁用，请重新登录！"
                notify.dingding_send(msg)
                notify.feishu_send(msg)
                self._detail(
                    "error",
                    f"验证登录态失败，账号已禁用：{account.nick_name}",
                    level="error",
                    success=False,
                    error_msg=resp.text[:300],
                )
                raise AccountError(f"刷新登录态失败: {resp.text[:300]}")
            except AccountError:
                raise
            except Exception as exc:
                attempt += 1
                logger.warning("刷新登录态出错(第%d次): %s", attempt, exc)
                time.sleep(3)
                if attempt >= max_retries:
                    self._detail(
                        "error",
                        f"验证登录态失败（重试 {max_retries} 次）：{account.nick_name}",
                        level="error",
                        success=False,
                        error_msg=str(exc),
                    )
                    raise AccountError(f"刷新登录态失败: {exc}")

    def refresh_skey_no_time(self, account: CnvpAccounts) -> None:
        """扫码回调后立即刷新登录态（不节流，对应 Java refSkeyAPPNoTime）。"""
        # 中转服务请求不再携带 token（兑换券配置已取消）
        url = f"{get_api_server_url()}/refSkeyAPPNoTime"
        resp = httpx.post(
            url,
            json=self._account_payload(account),
            timeout=30,
        )
        data = resp.json()
        if str(data.get("code")) == "0":
            account.cookie_value = data.get("data")
            self.db.commit()

    @staticmethod
    def _login_info(account: CnvpAccounts) -> dict:
        """从账号 cookie(JWT) 中解析出 loginInfo（含 accessToken、vid）。"""
        if not account.cookie_value:
            raise AccountError("账号 cookie 为空")
        # 中转服务通讯key（与中转服务约定一致，配置页只读）
        jwt_secret = get_config("api.middlewareKey", "MSKEY@!sYSA 2025-04-22 08:30:00")
        try:
            payload = jwt.decode(
                account.cookie_value,
                jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False, "verify_iss": False, "verify_exp": False},
            )
        except Exception:
            # 兼容外部服务使用不同密钥签发的情况：只解 payload 不验签
            payload = jwt.decode(account.cookie_value, options={"verify_signature": False})

        info = (payload.get("map") or {}).get("loginInfo")
        if isinstance(info, str):
            info = json.loads(info)
        if not isinstance(info, dict):
            raise AccountError("cookie 中缺少 loginInfo")
        return info

    def _weread_get(self, url: str, login_info: dict) -> str:
        """带 accessToken/vid 头请求微信读书接口；网络异常返回约定的标记串。"""
        headers = {
            "accessToken": str(login_info.get("accessToken", "")),
            "vid": str(login_info.get("vid", "")),
            "user-agent": _UA,
        }
        try:
            return _client.get(url, headers=headers).text
        except Exception as exc:
            logger.error("微信读书请求异常 %s: %s", url, exc)
            return f"zlzchat请求异常：{exc}"

    # ---------- 版本检测与文章拉取 ----------
    def check_version(self, account: CnvpAccounts, wxs_id: str) -> int:
        """读取公众号当前版本号（bookInfo.version）。"""
        login_info = self._login_info(account)
        vid = login_info.get("vid", "")
        url = (
            "https://i.weread.qq.com/book/readinfo"
            f"?vid={vid}&readingBookIndex=1&finishedBookIndex=1"
            f"&readingBookCount=1&finishedBookCount=1&bookId={wxs_id}&finishedDate=1"
        )
        text = self._weread_get(url, login_info)
        if "code: 401" in text:
            raise AccountError("readinfo 401", "401")
        if "zlzchat请求异常" in text:
            raise AccountError(text[:200])
        obj = json.loads(text)
        return int((obj.get("bookInfo") or {}).get("version", 0))

    def fetch_article_list(self, account: CnvpAccounts, wxs_id: str) -> list[dict]:
        """拉取公众号文章列表（reviews[].review.mpInfo），含 499/401 风控处理。"""
        login_info = self._login_info(account)
        url = f"https://i.weread.qq.com/book/articles?count=20&offset=0&bookId={wxs_id}&synckey=0"
        text = ""
        for attempt in range(3):
            text = self._weread_get(url, login_info)
            if "code: 499" in text:
                account.status = 3
                self.db.commit()
                time.sleep(5)
                continue
            if "code: 401" in text:
                account.status = 2
                self.db.commit()
                raise AccountError("articles 401", "401")
            break

        if "zlzchat请求异常" in text:
            account.status = 3
            self.db.commit()
            raise AccountError("zlzchat请求异常: " + text[:200])
        if "code: 499" in text or "code: 401" in text:
            raise AccountError("账号风控: " + text[:200])

        obj = json.loads(text)
        result: list[dict] = []
        for item in obj.get("reviews") or []:
            mp = ((item or {}).get("review") or {}).get("mpInfo") or {}
            if mp:
                result.append(mp)
        if result:
            account.status = 1
            self.db.commit()
        return result

    # ---------- 正文与封面 ----------
    @staticmethod
    def _decode_to_utf8(value: str | None) -> str:
        """解码 \\xHH 转义与 HTML 实体（对应 Java decodeToUtf8）。"""
        if not value:
            return ""

        def repl(match: re.Match) -> str:
            return chr(int(match.group(1), 16))

        step1 = re.sub(r"\\x([0-9A-Fa-f]{2})", repl, value)
        return html_lib.unescape(step1)

    @staticmethod
    def _filter_and_dedup_images(doc: BeautifulSoup) -> None:
        """过滤 wxapp.tc.qq.com 图片并按 URL 去重（保留首次出现）。"""
        seen: set[str] = set()
        for img in doc.select("img"):
            src = img.get("src") or img.get("data-src") or ""
            # 该域名的图片（多为装饰/占位）不存储
            if "wxapp.tc.qq.com" in src:
                img.decompose()
                continue
            if not src or not src.startswith(("http://", "https://")):
                continue
            if src in seen:
                img.decompose()
            else:
                seen.add(src)

        # embed / 背景图中的 wxapp.tc.qq.com 同样剔除
        for embed in doc.select("embed[src]"):
            if "wxapp.tc.qq.com" in embed.get("src", ""):
                embed.decompose()
        for element in doc.select("[style*='background-image']"):
            style = element.get("style", "")
            if "wxapp.tc.qq.com" in style:
                element["style"] = re.sub(
                    r"url\([^)]*wxapp\.tc\.qq\.com[^)]*\)", "", style
                )

    def fetch_content(self, wx_url: str) -> tuple[str, str]:
        """抓取微信文章正文，返回 (富文本HTML, 纯文本)。

        完整移植 Java WxReadCommon.getArticleInfo（直连微信原文）：
        - 补全浏览器请求头，避免被微信拦截返回空页
        - 普通正文取 #img-content；贴图/非常规文章用 cdn_url + description 正则兜底
        - 处理 data-src/embed/背景图，decodeToUtf8 解码转义
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://mp.weixin.qq.com/",
            "Connection": "keep-alive",
        }
        html = ""
        # 直连微信原文（getArticleInfo）；偶发空返回时重试
        for attempt in range(3):
            try:
                html = httpx.get(wx_url, headers=headers, timeout=30, follow_redirects=True).text
                # 命中验证/空页时视为失败，稍后重试
                if html and "验证" not in html[:500] and len(html) > 500:
                    break
            except Exception as exc:
                logger.warning("抓取正文请求失败(第%d次) %s: %s", attempt + 1, wx_url, exc)
            html = ""
            time.sleep(1)

        if not html:
            return "<p></p>", ""

        try:
            # 与 Java 一致：解析前先清洗 1px 隐藏样式
            soup = BeautifulSoup(html.replace("width: 1px !important", ""), "lxml")
            img_contents = soup.select("#img-content")

            if img_contents:
                # 普通正文：拼接各处 img-content，去掉隐藏样式
                inner = "".join(
                    node.decode_contents().replace("visibility: hidden; opacity: 0; ", "")
                    for node in img_contents
                )
                doc = BeautifulSoup(inner, "lxml")
            else:
                # 贴图 / 非常规文章：从脚本中提取 cdn_url 图片与 description 文案
                imgs = ""
                for cdn_url in re.findall(r"cdn_url:\s*'([^']+)'", html):
                    decoded = cdn_url.replace("\\x26amp;", "&")
                    imgs += f"<img data-src='{decoded}' style='width:100%;'>"
                meta = soup.select_one("meta[name=description]")
                description = (meta.get("content", "") if meta else "").replace("\\x0a", "<br/>")
                if not description:
                    match = re.search(r"content:\s*'([^']*)'", html)
                    if match:
                        description = match.group(1).replace("\\x0a", "<br>")
                rebuilt = f"<p>{self._decode_to_utf8(description)}{imgs}</p>"
                doc = BeautifulSoup(rebuilt, "lxml")

            # 图片资源：data-src / src / embed / 背景图统一用可访问地址
            for img in doc.select("img[data-src]"):
                src = img.get("data-src", "")
                if src.startswith(("http://", "https://")):
                    img["src"] = src
                    img["data-src"] = src
            for embed in doc.select("embed[src]"):
                src = embed.get("src", "")
                if src.startswith(("http://", "https://")):
                    embed["src"] = src
            for element in doc.select("[style*='background-image']"):
                style = element.get("style", "")
                match = re.search(r"url\(([^)]+)\)", style)
                if match:
                    url = match.group(1).strip('"\'')
                    if url.startswith(("http://", "https://")):
                        element["style"] = style.replace(url, url)

            # 过滤 wxapp.tc.qq.com 图片（无需存储）+ 重复图片地址去重
            self._filter_and_dedup_images(doc)

            body = doc.find("body")
            if body is None:
                return "<p></p>", ""
            return body.decode_contents(), body.get_text("\n", strip=True)
        except Exception as exc:
            logger.warning("解析正文失败 %s: %s", wx_url, exc)
            return "<p></p>", ""

    def download_cover(self, url: str, wxs_id: str, original_id: str) -> str:
        """下载封面到本地，返回可访问路径；失败则回退原 URL。"""
        if not url:
            return ""
        try:
            folder = _UPLOAD_DIR / wxs_id / original_id
            folder.mkdir(parents=True, exist_ok=True)
            resp = _client.get(url)
            suffix = ".jpg"
            if "png" in resp.headers.get("content-type", ""):
                suffix = ".png"
            filename = f"{uuid.uuid4().hex}{suffix}"
            (folder / filename).write_bytes(resp.content)
            return f"/uploadGZHFile/{wxs_id}/{original_id}/{filename}"
        except Exception as exc:
            logger.warning("下载封面失败 %s: %s", url, exc)
            return url

    # ---------- 公众号添加（搜索 / 链接解析） ----------
    def pick_account(self) -> CnvpAccounts:
        """随机取一个可用微信账号（对应 Java ORDER BY RAND() LIMIT 1）。"""
        accounts = self._select_accounts()
        if not accounts:
            raise AccountError("无可用账号！请先通过扫码添加微信读书账号")
        return random.choice(accounts)

    def _mark_disabled(self, account: CnvpAccounts) -> None:
        account.status = 2
        self.db.commit()

    def search_feed(self, feed_name: str) -> list[dict]:
        """按公众号名称搜索微信读书书籍（对应 Java searchFeed）。

        返回 books 数组，每个元素形如 {"bookInfo": {...}}，前端据此展示并选择。
        """
        if not feed_name or len(feed_name) < 2:
            raise AccountError("公众号字符应大于两位")
        account = self.pick_account()
        self.refresh_skey(account)
        login_info = self._login_info(account)
        url = (
            "https://i.weread.qq.com/store/search"
            f"?v=2&scope=2&count=15&type=0&keyword={quote(feed_name, safe='')}"
        )
        text = self._weread_get(url, login_info)
        if "code: 401" in text:
            self._mark_disabled(account)
            raise AccountError("账号登录态失效，已禁用，请重新扫码登录")
        if "zlzchat请求异常" in text:
            raise AccountError(text[:200])
        obj = json.loads(text)
        return obj.get("books") or []

    def download_feed_cover(self, url: str) -> str:
        """下载公众号封面到 uploadGZHCover 目录，返回可访问路径（对应 Java FileUploadUtils）。"""
        if not url:
            return ""
        try:
            folder = DATA_DIR / "uploadGZHCover"
            folder.mkdir(parents=True, exist_ok=True)
            resp = _client.get(url)
            suffix = ".png" if "png" in resp.headers.get("content-type", "") else ".jpg"
            filename = f"{uuid.uuid4().hex}{suffix}"
            (folder / filename).write_bytes(resp.content)
            return f"/uploadGZHCover/{filename}"
        except Exception as exc:
            logger.warning("下载公众号封面失败 %s: %s", url, exc)
            return url

    def add_feed_from_search(self, feed_info: dict) -> dict:
        """将搜索结果中的 bookInfo 保存为订阅源（对应 Java addFeed）。"""
        book_info = feed_info.get("bookInfo") or feed_info
        wxs_id = str(book_info.get("bookId", "") or "")
        if not wxs_id:
            raise AccountError("无效的公众号数据")
        if self.db.query(CnvpFeeds).filter(CnvpFeeds.wxs_id == wxs_id).first():
            raise AccountError("该公众号已添加！")
        row = CnvpFeeds(
            feed_id=uuid.uuid4().hex,
            wxs_id=wxs_id,
            mp_name=str(book_info.get("title", "") or ""),
            mp_cover=self.download_feed_cover(str(book_info.get("cover", "") or "")),
            mp_intro=str(book_info.get("intro", "") or ""),
            status=2,
            show_count=20,
            update_count=0,
            is_deleted=0,
        )
        self.db.add(row)
        self.db.commit()
        return {"wxsId": wxs_id, "mpName": row.mp_name}

    def add_feed_from_link(self, link_url: str) -> dict:
        """根据文章链接解析并添加订阅源（对应 Java addLinkFeed）。

        流程：mp/getreviewid 取 reviewId → 正则提取 MP_WXS_xxx → book/readinfo 取详情。
        """
        if not link_url or not link_url.strip():
            raise AccountError("请输入文章链接")
        account = self.pick_account()
        self.refresh_skey(account)
        login_info = self._login_info(account)
        headers = {
            "accessToken": str(login_info.get("accessToken", "")),
            "vid": str(login_info.get("vid", "")),
            "user-agent": _UA,
        }

        # 1) 解析文章链接得到 reviewId
        response = _client.post(
            "https://i.weread.qq.com/mp/getreviewid",
            json={"urls": [link_url.strip()]},
            headers=headers,
        )
        text = response.text
        if "code: 401" in text:
            self._mark_disabled(account)
            raise AccountError("账号禁用！请重新扫码登录")
        if "zlzchat请求异常" in text:
            raise AccountError(text[:200])
        review_ids = (json.loads(text).get("reviewIds") or [])
        if not review_ids:
            raise AccountError("链接异常：未解析到公众号")
        wxs_id = str(review_ids[0].get("reviewId", "") or "")
        match = re.match(r"^(MP_WXS_\d+)", wxs_id)
        if not match:
            raise AccountError("链接异常！")
        wxs_id = match.group(1)

        if self.db.query(CnvpFeeds).filter(CnvpFeeds.wxs_id == wxs_id).first():
            raise AccountError("该公众号已添加！")

        # 2) 读取公众号详情
        vid = str(login_info.get("vid", ""))
        url = (
            "https://i.weread.qq.com/book/readinfo"
            f"?vid={vid}&readingBookIndex=1&finishedBookIndex=1"
            f"&readingBookCount=1&finishedBookCount=1&bookId={wxs_id}&finishedDate=1"
        )
        text = self._weread_get(url, login_info)
        if "code: 401" in text:
            self._mark_disabled(account)
            raise AccountError("账号登录态失效，已禁用，请重新扫码登录")
        if "zlzchat请求异常" in text:
            raise AccountError(text[:200])
        book_info = (json.loads(text).get("bookInfo") or {})
        row = CnvpFeeds(
            feed_id=uuid.uuid4().hex,
            wxs_id=wxs_id,
            mp_name=str(book_info.get("title", "") or ""),
            mp_cover=self.download_feed_cover(str(book_info.get("cover", "") or "")),
            mp_intro=str(book_info.get("intro", "") or ""),
            status=2,
            show_count=20,
            update_count=0,
            is_deleted=0,
        )
        self.db.add(row)
        self.db.commit()
        return {"wxsId": wxs_id, "mpName": row.mp_name}

    # ---------- 文章入库 ----------
    def save_articles(self, feed: CnvpFeeds, mp_list: list[dict]) -> int:
        """按 original_id 去重入库，返回新增数量。"""
        articlecont = get_config("api.articlecont") == "1"
        added = 0
        for mp in mp_list:
            original_id = str(mp.get("originalId", "")).replace("~", "_")
            if not original_id:
                continue
            if self.db.query(CnvpMpArticles).filter_by(original_id=original_id).first():
                continue

            title = str(mp.get("title", "") or "")
            if len(title) > 200:
                title = title[:50] + "..."
            link = f"https://mp.weixin.qq.com/s/{original_id}"
            article = CnvpMpArticles(
                articles_id=uuid.uuid4().hex,
                original_id=original_id,
                wxs_id=feed.wxs_id,
                title=title,
                links=link,
                doc_url=link,
                pic_url=self.download_cover(str(mp.get("pic_url", "")), feed.wxs_id or "", original_id),
                read_type="0",
            )
            # 发布时间：秒级时间戳
            try:
                ts = int(mp.get("time", 0))
                if ts:
                    article.publish_time = datetime.fromtimestamp(ts)
            except (ValueError, TypeError):
                pass

            if articlecont:
                content, content_text = self.fetch_content(link)
                if content == "<p></p>":
                    content = title.replace("\n", "<br>")
                    content_text = content
                article.content = content
                article.content_text = content_text

            self.db.add(article)
            self.db.commit()
            added += 1
            feed.sync_time = datetime.now()
        if added:
            feed.update_count = (feed.update_count or 0) + added
            self.db.commit()
        return added

    def sync_feed(self, account: CnvpAccounts, feed: CnvpFeeds) -> dict:
        """同步单个公众号的最新文章（不做版本检测）。"""
        self._detail(
            "fetch_start",
            f"开始执行拉取：{feed.mp_name}",
            feed_name=feed.mp_name,
            wxs_id=feed.wxs_id,
        )
        self.refresh_skey(account)
        mp_list = self.fetch_article_list(account, feed.wxs_id or "")
        added = self.save_articles(feed, mp_list)
        self._detail(
            "fetched",
            f"已拉取 {added} 条：{feed.mp_name}",
            feed_name=feed.mp_name,
            wxs_id=feed.wxs_id,
        )
        return {
            "rlt": True,
            "updateNum": added,
            "mp_list": mp_list,
            "feed_name": feed.mp_name,
        }

    # ---------- 主流程 ----------
    def _select_accounts(self) -> list[CnvpAccounts]:
        return (
            self.db.query(CnvpAccounts)
            .filter(
                CnvpAccounts.category == "1",
                CnvpAccounts.status.in_([1, 3]),
                CnvpAccounts.is_deleted == 0,
            )
            .order_by(func_random())
            .all()
        )

    def _select_feeds(self, job: SysJob | None) -> list[CnvpFeeds]:
        wxs_ids: list[str] = []
        if job and job.classification_id:
            ids = [int(x) for x in job.classification_id if str(x).isdigit()]
            if ids:
                details = (
                    self.db.query(CnvpMpClassificationDetail)
                    .filter(CnvpMpClassificationDetail.classification_id.in_(ids))
                    .all()
                )
                wxs_ids.extend(d.wxs_id for d in details if d.wxs_id)
        if job and job.wxs_id:
            wxs_ids.extend(str(x) for x in job.wxs_id if x)
        wxs_ids = list(dict.fromkeys(wxs_ids))  # 去重保序

        query = self.db.query(CnvpFeeds).filter(CnvpFeeds.status == 2, CnvpFeeds.is_deleted == 0)
        if wxs_ids:
            query = query.filter(CnvpFeeds.wxs_id.in_(wxs_ids))
        return query.order_by(CnvpFeeds.version.asc(), func_random()).all()

    def update_all(self, job: SysJob | None, log_id: int) -> dict:
        """定时任务主流程：拉取全部（或任务指定范围）公众号文章。

        账号策略、断点续传、飞书钉钉通知、同步状态复位、异常记录全部保留。
        不做执行前防重入检查，允许同一任务并发执行。
        """
        started = time.time()
        total_added = 0
        updated_count = 0  # 实际更新(拉取)的公众号数
        skipped_count = 0  # 版本未变化跳过(无需更新)的公众号数
        new_articles: list[tuple[str, str]] = []
        error_msg = ""
        progress_key = f"job:{job.job_id if job else 0}"

        try:
            self._begin_detail(
                "job",
                job_id=job.job_id if job else None,
                job_name=job.job_name if job else "定时任务",
                message=f"定时任务请求发起，开始执行：{job.job_name if job else '定时任务'}",
            )
            notify.notify_start()
            base_wait = get_config_int("api.updateFeedTime", 60) * 1000

            accounts = self._select_accounts()
            if not accounts:
                raise AccountError("无可用账号！")
            feeds = self._select_feeds(job)
            available = [a for a in accounts if a.status != 2]
            if not available:
                raise AccountError("无可用账号！")

            is_failover = bool(job and job.acount_type == "1")
            check_update = get_config("api.checkFeedUpdate") == "1"
            current = 0
            start_index = _progress.get(progress_key, 0)

            for index in range(start_index, len(feeds)):
                feed = feeds[index]
                self._detail(
                    "feed_start",
                    f"开始更新公众号：{feed.mp_name}（{feed.wxs_id}）",
                    feed_name=feed.mp_name,
                    wxs_id=feed.wxs_id,
                )
                success = False
                while not success:
                    if not is_failover:
                        current = (current + 1) % len(available)
                    account = available[current]
                    try:
                        self.refresh_skey(account)
                        version = self.check_version(account, feed.wxs_id or "")
                        need_update = (
                            not feed.version
                            or not check_update
                            or (check_update and version > int(feed.version or 0))
                        )
                        if need_update:
                            feed.version = str(version)
                            result = self.sync_feed(account, feed)
                            success = bool(result["rlt"])
                            if not success:
                                raise AccountError("同步失败")
                            added = result["updateNum"]
                            total_added += added
                            for mp in result["mp_list"]:
                                title = str(mp.get("title", ""))
                                if len(title) > 200:
                                    title = title[:50] + "..."
                                new_articles.append(
                                    (
                                        feed.mp_name,
                                        f"https://mp.weixin.qq.com/s/"
                                        f"{str(mp.get('originalId', '')).replace('~', '_')}",
                                    )
                                )
                            self._update_log(log_id, total_added)
                            updated_count += 1
                            logger.info("%s:处理成功(新增%d篇)", feed.mp_name, added)
                            time.sleep((base_wait + random.randint(0, 3000)) / 1000)
                        else:
                            success = True
                            skipped_count += 1
                            logger.info("%s:无需更新", feed.mp_name)
                            self._detail(
                                "no_update",
                                f"{feed.mp_name}：无需更新（版本未变化，跳过）",
                                feed_name=feed.mp_name,
                                wxs_id=feed.wxs_id,
                            )
                            time.sleep((3000 + random.randint(0, 3000)) / 1000)
                        _progress[progress_key] = index + 1
                    except Exception as exc:
                        logger.warning("处理 %s 出错: %s", feed.mp_name, exc)
                        self._detail(
                            "error",
                            f"处理 {feed.mp_name} 出错：{exc}",
                            level="error",
                            success=False,
                            error_msg=str(exc),
                            feed_name=feed.mp_name,
                            wxs_id=feed.wxs_id,
                        )
                        available.remove(account)
                        if not available:
                            raise AccountError("账号被风控，请前往手机端手动解除后重新执行定时任务！")
                        current = current % len(available)

            if new_articles:
                notify.notify_summary(new_articles)
            self._finish_log(log_id, total_added)
            _progress.pop(progress_key, None)
            result = {"code": 200, "msg": "执行完成", "updateNum": total_added}
        except Exception as exc:
            error_msg = str(exc)
            logger.exception("定时任务执行异常")
            self._detail(
                "error",
                f"定时任务执行异常：{error_msg}",
                level="error",
                success=False,
                error_msg=error_msg,
            )
            self._finish_log(log_id, total_added, success=False, error=error_msg)
            notify.notify_error(error_msg, get_config("api.apiKey"))
            result = {"code": 500, "msg": error_msg, "updateNum": total_added}
        finally:
            job_name = job.job_name if job else "最新同步"
            write_log(
                log_type="job",
                description=(
                    f"定时任务执行: {job_name}（更新{updated_count}个/无需更新{skipped_count}个"
                    f"/新增{total_added}篇）"
                ),
                user_name="system",
                status_code=result.get("code", 500),
                success=result.get("code", 200) == 200,
                error_msg=error_msg or None,
                cost_time=int((time.time() - started) * 1000),
            )
            self._end_detail(
                f"任务结束：更新{updated_count}个/无需更新{skipped_count}个/新增{total_added}篇"
                f"，耗时{int((time.time() - started) * 1000)}ms",
                success=result.get("code", 200) == 200,
                error_msg=error_msg or None,
            )
        return result

    def sync_latest(self, wxs_id: str, log_id: int | None = None) -> dict:
        """手动同步指定公众号最新文章（写 log_catagory=2 记录）。"""
        started = time.time()
        own_log = log_id is None
        if own_log:
            log_id = self._new_log("2", wxs_id=wxs_id)
        error_msg = ""
        added_num = 0
        try:
            self._begin_detail(
                "latest",
                wxs_id=wxs_id,
                job_name="最新拉取",
                message=f"最新拉取开始：{wxs_id}",
            )
            feed = (
                self.db.query(CnvpFeeds)
                .filter(CnvpFeeds.wxs_id == wxs_id, CnvpFeeds.is_deleted == 0)
                .first()
            )
            if not feed:
                raise AccountError(f"公众号不存在: {wxs_id}")
            self._batch_ctx["feed_name"] = feed.mp_name
            accounts = self._select_accounts()
            if not accounts:
                raise AccountError("无可用账号！")
            result = self.sync_feed(accounts[0], feed)
            added_num = result["updateNum"]
            if own_log:
                self._finish_log(log_id, added_num)
            return ok_result(added_num)
        except Exception as exc:
            error_msg = str(exc)
            self._detail(
                "error",
                f"最新拉取出错：{error_msg}",
                level="error",
                success=False,
                error_msg=error_msg,
            )
            if own_log:
                self._finish_log(log_id, 0, success=False, error=error_msg)
            return {"code": 500, "msg": error_msg, "data": None}
        finally:
            write_log(
                log_type="job",
                description=f"最新同步: {wxs_id}",
                user_name="system",
                success=not error_msg,
                error_msg=error_msg or None,
                cost_time=int((time.time() - started) * 1000),
            )
            self._end_detail(
                f"最新拉取结束：新增{added_num}篇，耗时{int((time.time() - started) * 1000)}ms",
                success=not error_msg,
                error_msg=error_msg or None,
            )

    def sync_history(
        self, wxs_id: str, his_type: int | str = 1, start: int = 0, end: int = 0
    ) -> dict:
        """历史文章同步（对应 Java WxReadCommon.getFeedArticle）。

        his_type=1：从数据库记录的 update_count（最后拉取页）续拉，每页 offset +20，
                    拉完回写 update_count，直到某页无文章为止。
        his_type=2：自定义，从 start 拉到 end，每页 offset +20。
        """
        started = time.time()
        his_type = int(his_type or 1)
        start = int(start or 0)
        end = int(end or 0)
        log_id = self._new_log("3", wxs_id=wxs_id, history_start=start, history_end=end)
        error_msg = ""
        added = 0
        start_page = 0
        end_page = 0
        try:
            self._begin_detail(
                "history",
                wxs_id=wxs_id,
                job_name="历史同步",
                message=(
                    f"历史记录同步开始：类型{his_type}，开始页{start}，结束页{end}"
                ),
            )
            feed = (
                self.db.query(CnvpFeeds)
                .filter(CnvpFeeds.wxs_id == wxs_id, CnvpFeeds.is_deleted == 0)
                .first()
            )
            if not feed:
                raise AccountError(f"公众号不存在: {wxs_id}")
            self._batch_ctx["feed_name"] = feed.mp_name
            accounts = self._select_accounts()
            if not accounts:
                raise AccountError("无可用账号！")
            account = accounts[0]
            self.refresh_skey(account)

            # 初始 offset：类型1 从数据库最后拉取页续拉；类型2 从用户输入开始页
            page = int(feed.update_count or 0) if his_type == 1 else start
            start_page = page
            end_page = page
            self._detail("fetch_start", f"从第 {page} 页开始拉取（类型{his_type}）")

            while True:
                login_info = self._login_info(account)
                url = (
                    f"https://i.weread.qq.com/book/articles"
                    f"?count=20&offset={page}&bookId={wxs_id}&synckey=0"
                )
                text = self._weread_get(url, login_info)
                if "code: 401" in text:
                    self._mark_disabled(account)
                    raise AccountError("账号登录态失效，已禁用，请重新扫码登录")
                if "zlzchat请求异常" in text or "code: 499" in text:
                    self._detail(
                        "warning",
                        f"接口返回异常，停止拉取：{text[:80]}",
                        level="warning",
                    )
                    break

                reviews = json.loads(text).get("reviews") or []
                mp_list = [((i.get("review") or {}).get("mpInfo")) for i in reviews]
                mp_list = [m for m in mp_list if m]
                if not mp_list:
                    self._detail("no_update", f"第 {page} 页无文章，拉取结束")
                    break
                added += self.save_articles(feed, mp_list)
                end_page = page
                self._detail(
                    "fetched",
                    f"第 {page} 页拉取 {len(mp_list)} 篇，累计新增 {added} 篇",
                )

                if his_type == 1:
                    # 全部拉取：回写最后拉取页，继续下一页直到无文章
                    feed.update_count = page
                    self.db.commit()
                elif his_type == 2 and page >= end:
                    # 自定义：达到结束页即停止
                    break

                page += 20

            self._finish_log(log_id, added)
            return ok_result(added)
        except Exception as exc:
            error_msg = str(exc)
            self._detail(
                "error",
                f"历史同步出错了：{error_msg}",
                level="error",
                success=False,
                error_msg=error_msg,
            )
            self._finish_log(log_id, added, success=False, error=error_msg)
            return {"code": 500, "msg": error_msg, "data": None}
        finally:
            # 同步日志的起止页回写到记录
            log = self.db.get(CnvpUpdateLog, log_id)
            if log:
                log.history_start_num = start_page
                log.history_end_num = end_page
                self.db.commit()
            write_log(
                log_type="job",
                description=f"历史同步: {wxs_id}",
                user_name="system",
                success=not error_msg,
                error_msg=error_msg or None,
                cost_time=int((time.time() - started) * 1000),
            )
            self._end_detail(
                f"历史同步结束：第{start_page}页~第{end_page}页，新增{added}篇"
                f"，耗时{int((time.time() - started) * 1000)}ms",
                success=not error_msg,
                error_msg=error_msg or None,
            )

    # ---------- update_log 辅助 ----------
    def _new_log(
        self,
        category: str,
        feed_name: str = "",
        history_start: int = 0,
        history_end: int = 0,
        wxs_id: str = "",
    ) -> int:
        # 优先用传入名称；否则按 wxs_id 反查公众号中文名，更新记录展示名称而非 ID
        if not feed_name and wxs_id:
            feed = (
                self.db.query(CnvpFeeds)
                .filter(CnvpFeeds.wxs_id == wxs_id, CnvpFeeds.is_deleted == 0)
                .first()
            )
            feed_name = feed.mp_name if feed and feed.mp_name else wxs_id
        log = CnvpUpdateLog(
            log_sta="1",
            log_result_sta="0",
            log_catagory=category,
            update_num=0,
            feed_name=feed_name,
            history_start_num=history_start,
            history_end_num=history_end,
        )
        self.db.add(log)
        self.db.commit()
        return log.log_id

    def _update_log(self, log_id: int, update_num: int) -> None:
        log = self.db.get(CnvpUpdateLog, log_id)
        if log:
            log.update_num = update_num
            self.db.commit()

    def _finish_log(self, log_id: int, update_num: int, success: bool = True, error: str = "") -> None:
        log = self.db.get(CnvpUpdateLog, log_id)
        if log:
            log.update_num = update_num
            log.log_sta = "2"
            log.log_result_sta = "1" if success else "2"
            if error:
                log.remark = error[:4000]
            self.db.commit()


def ok_result(update_num: int) -> dict:
    return {"code": 200, "msg": "ok", "data": {"updateNum": update_num}}


def func_random():
    """ORDER BY RAND() 的跨方言实现：SQLite 用 random()，MySQL 用 rand()。"""
    from sqlalchemy import func

    return func.random() if settings.is_sqlite else func.rand()
