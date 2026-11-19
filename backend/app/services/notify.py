"""飞书、钉钉通知服务。

飞书/钉钉加签与消息格式：
- 钉钉：毫秒时间戳 + HmacSHA256(secret, "ts\\nsecret") + Base64 + URLEncode
- 飞书：秒时间戳   + HmacSHA256(key="ts\\nsecret", data=空字节) + Base64
配置均从 sys_config 读取（api.dingdingToken/api.dingdingSecret/api.feishuUrl/api.feishuSecret）。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Iterable

import httpx

from app.services.config_service import get_config

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0"


def _ding_ding_config() -> tuple[str, str]:
    return get_config("api.dingdingToken"), get_config("api.dingdingSecret")


def _feishu_config() -> tuple[str, str]:
    return get_config("api.feishuUrl"), get_config("api.feishuSecret")


def _hmac_base64(key: bytes, data: bytes) -> str:
    return base64.b64encode(hmac.new(key, data, hashlib.sha256).digest()).decode()


def dingding_sign(secret: str, timestamp_ms: int) -> str:
    """钉钉加签：key=secret，data=timestamp + 换行 + secret，结果再 URLEncode。"""
    string_to_sign = f"{timestamp_ms}\n{secret}"
    sign = _hmac_base64(secret.encode("utf-8"), string_to_sign.encode("utf-8"))
    return urllib.parse.quote_plus(sign)


def feishu_sign(secret: str, timestamp_s: int) -> str:
    """飞书加签：key=timestamp + 换行 + secret，data=空字节。"""
    string_to_sign = f"{timestamp_s}\n{secret}"
    return _hmac_base64(string_to_sign.encode("utf-8"), b"")


def _post_json(url: str, payload: dict, timeout: float = 10.0) -> bool:
    try:
        resp = httpx.post(url, json=payload, timeout=timeout, headers={"User-Agent": _UA})
        return resp.status_code == 200
    except Exception as exc:  # 通知失败不应影响主流程
        logger.warning("通知发送失败: %s", exc)
        return False


def dingding_send(msg: str) -> bool:
    """钉钉文本通知。"""
    token, secret = _ding_ding_config()
    if not token or not secret:
        return False
    ts = int(time.time() * 1000)
    url = (
        "https://oapi.dingtalk.com/robot/send"
        f"?access_token={token}&timestamp={ts}&sign={dingding_sign(secret, ts)}"
    )
    payload = {
        "msgtype": "text",
        "text": {"content": msg},
        "at": {"isAtAll": True},
    }
    return _post_json(url, payload)


def dingding_markdown(title: str, text: str) -> bool:
    """钉钉 Markdown 通知。"""
    token, secret = _ding_ding_config()
    if not token or not secret:
        return False
    ts = int(time.time() * 1000)
    url = (
        "https://oapi.dingtalk.com/robot/send"
        f"?access_token={token}&timestamp={ts}&sign={dingding_sign(secret, ts)}"
    )
    payload = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
        "at": {"isAtAll": True},
    }
    return _post_json(url, payload)


def feishu_send(msg: str) -> bool:
    """飞书文本通知。"""
    url, secret = _feishu_config()
    if not url or not secret:
        return False
    ts = int(time.time())
    payload = {
        "msg_type": "text",
        "timestamp": str(ts),
        "sign": feishu_sign(secret, ts),
        "content": {"text": f'{msg} <at user_id="all">所有人</at>'},
    }
    return _post_json(url, payload)


def feishu_post(articles: Iterable[tuple[str, str]], title: str = "") -> bool:
    """飞书富文本(post)通知：第一行为标题，其后为文章链接，末尾 @所有人。"""
    url, secret = _feishu_config()
    if not url or not secret:
        return False
    articles = list(articles)
    if not articles:
        return feishu_send("更新完成，暂无新文章")

    ts = int(time.time())
    content: list[list[dict]] = [[{"tag": "text", "text": title or "文章列表"}]]
    link_group: list[dict] = []
    for article_title, link in articles:
        link_group.append({"tag": "a", "text": article_title, "href": link})
    content.append(link_group)
    content.append([{"tag": "at", "user_id": "all", "user_name": "所有人"}])

    payload = {
        "msg_type": "post",
        "timestamp": str(ts),
        "sign": feishu_sign(secret, ts),
        "content": {"post": {"zh_cn": {"title": title, "content": content}}},
    }
    return _post_json(url, payload)


def notify_start() -> None:
    """任务开始通知。"""
    dingding_send("定时拉取开始")
    feishu_send("定时拉取开始")


def notify_summary(articles: Iterable[tuple[str, str]], title: str = "文章列表") -> None:
    """汇总通知：钉钉 Markdown + 飞书富文本。"""
    articles = list(articles)
    md_lines = [f"### {title}"]
    for idx, (article_title, link) in enumerate(articles, start=1):
        md_lines.append(f"{idx}. [{article_title}]({link})")
    dingding_markdown(title, "\n".join(md_lines))
    feishu_post(articles, title)


def notify_error(msg: str, api_key: str = "") -> None:
    """异常通知，可选附带手动触发链接。"""
    text = msg
    if api_key:
        text += f"\n\n手动解除后可点击链接重新拉取：/api/open/updateFeedAll?key={api_key}"
    dingding_send(text)
    feishu_send(text)
