# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import asyncio
import random
from typing import Any, Awaitable, Callable, Dict, List, Optional

from playwright.async_api import Page

from tools import utils


class TaobaoDataFetchError(RuntimeError):
    """Raised when Taobao rejects or cannot complete a comment request."""


class TaobaoRiskControlError(TaobaoDataFetchError):
    """Raised when Taobao blocks the current browser session or request rate."""


class TaobaoClient:
    PAGE_SIZE = 20
    MAX_TRANSIENT_RETRIES = 2

    def __init__(self, page: Page) -> None:
        self.page = page
        self.last_stop_reason: Optional[str] = None

    @staticmethod
    def _is_risk_control_error(error: BaseException) -> bool:
        message = str(error).lower()
        return any(
            marker in message
            for marker in (
                "fail_sys_user_validate",
                "fail_sys_session_expired",
                "fail_sys_token_expired",
                "fail_sys_illegal_access",
                "fail_sys_traffic_limit",
                "rgv587_error",
                "验证码",
                "需要登录",
                "访问受限",
                "访问过于频繁",
                "挤爆啦",
                "风控",
            )
        )

    @staticmethod
    def _is_transient_error(error: BaseException) -> bool:
        message = str(error).lower()
        return any(
            marker in message
            for marker in (
                "timeout",
                "timed out",
                "net::err_",
                "http 500",
                "http 502",
                "http 503",
                "http 504",
            )
        )

    async def _get_comment_page_with_retry(
        self, item_id: str, biz_code: str, page_number: int
    ) -> Dict[str, Any]:
        for attempt in range(self.MAX_TRANSIENT_RETRIES + 1):
            try:
                return await self.get_comment_page(item_id, biz_code, page_number)
            except Exception as exc:
                if self._is_risk_control_error(exc):
                    raise TaobaoRiskControlError(str(exc)) from exc
                if isinstance(exc, TaobaoDataFetchError):
                    raise
                if (
                    not self._is_transient_error(exc)
                    or attempt == self.MAX_TRANSIENT_RETRIES
                ):
                    raise TaobaoDataFetchError(f"淘宝评论请求失败：{exc}") from exc

                retry_delay = random.uniform(
                    5.0 * (2**attempt),
                    10.0 * (2**attempt),
                )
                utils.logger.warning(
                    f"[TaobaoClient] 商品 {item_id} 第 {page_number} 页请求异常，"
                    f"{retry_delay:.1f} 秒后进行第 {attempt + 1} 次重试"
                )
                await asyncio.sleep(retry_delay)

        raise TaobaoDataFetchError("淘宝评论请求重试状态异常")

    async def get_comment_page(
        self, item_id: str, biz_code: str, page_number: int
    ) -> Dict[str, Any]:
        """Fetch one signed comment page through Taobao's loaded MTOP runtime."""
        response = await self.page.evaluate(
            """
            async ({itemId, bizCode, pageNumber, pageSize}) => {
                if (typeof window.lib?.mtop?.request !== "function") {
                    throw new Error("淘宝 MTOP 请求环境未加载");
                }
                try {
                    return await window.lib.mtop.request({
                        api: "mtop.alibaba.review.list.for.new.pc.detail",
                        v: "1.0",
                        ttid: "2022@taobao_litepc_9.17.0",
                        AntiFlood: true,
                        AntiCreep: true,
                        timeout: 20000,
                        data: {
                            itemId,
                            bizCode,
                            channel: "pc_detail",
                            pageSize,
                            pageNum: pageNumber,
                            orderType: ""
                        }
                    });
                } catch (error) {
                    if (error && typeof error === "object" && error.ret) {
                        return error;
                    }
                    throw error;
                }
            }
            """,
            {
                "itemId": item_id,
                "bizCode": biz_code,
                "pageNumber": page_number,
                "pageSize": self.PAGE_SIZE,
            },
        )
        if not isinstance(response, dict):
            raise TaobaoDataFetchError("淘宝评论接口返回了无法识别的数据")

        ret = response.get("ret") or []
        ret_message = str(ret[0]) if isinstance(ret, list) and ret else ""
        if not ret_message.startswith("SUCCESS::"):
            return {"code": ret_message or "UNKNOWN", "message": ret_message}

        data = response.get("data")
        module = data.get("module") if isinstance(data, dict) else None
        if not isinstance(module, dict):
            raise TaobaoDataFetchError("淘宝评论接口缺少 data.module 数据")
        review_list = module.get("reviewVOList")
        if not isinstance(review_list, list):
            raise TaobaoDataFetchError("淘宝评论接口缺少 reviewVOList 数据")

        comments = [self._normalize_api_comment(item) for item in review_list]
        has_next = str(module.get("hasNext", "false")).lower() == "true"
        return {
            "code": "SUCCESS",
            "message": ret_message,
            "hasNext": has_next,
            "commentList": comments,
        }

    @staticmethod
    def _normalize_api_comment(comment: Any) -> Dict[str, Any]:
        if not isinstance(comment, dict) or not comment.get("id"):
            raise TaobaoDataFetchError("淘宝评论数据缺少评论 ID")

        interaction = comment.get("interactionVO") or {}
        append = comment.get("reviewAppendVO") or {}
        sku_text = comment.get("skuText") or {}
        if not isinstance(interaction, dict) or not isinstance(append, dict):
            raise TaobaoDataFetchError("淘宝评论交互或追评数据格式异常")
        if not isinstance(sku_text, dict):
            raise TaobaoDataFetchError("淘宝评论 SKU 数据格式异常")

        pictures = comment.get("reviewPicPathList") or []
        append_pictures = append.get("reviewPicPathList") or []
        if not isinstance(pictures, list) or not isinstance(append_pictures, list):
            raise TaobaoDataFetchError("淘宝评论图片数据格式异常")

        return {
            "comment_id": str(comment["id"]),
            "content": comment.get("reviewWordContent", ""),
            "score": None,
            "create_time": comment.get("reviewDate", ""),
            "user_id": "",
            "nickname": comment.get("userNick", ""),
            "avatar": comment.get("headPicUrl", ""),
            "sku_info": " / ".join(str(value) for value in sku_text.values()),
            "pictures": [str(url) for url in pictures if url],
            "like_count": interaction.get("likeCount", 0),
            "reply_content": comment.get("reply", ""),
            "append_content": append.get("appendedWordContent", ""),
            "append_time": append.get("intervalDay", ""),
            "append_pictures": [str(url) for url in append_pictures if url],
            "raw_comment": comment,
        }

    async def get_comments(
        self,
        item_id: str,
        biz_code: str,
        max_count: int,
        start_page: int,
        callback: Optional[
            Callable[[str, List[Dict[str, Any]]], Awaitable[None]]
        ] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch comments page by page and persist each page before continuing."""
        if start_page < 1:
            raise ValueError("淘宝评论起始页必须大于等于 1")
        if max_count <= 0:
            return []

        self.last_stop_reason = None
        comments: List[Dict[str, Any]] = []
        page_number = start_page
        while len(comments) < max_count:
            try:
                response = await self._get_comment_page_with_retry(
                    item_id, biz_code, page_number
                )
            except TaobaoRiskControlError as exc:
                self.last_stop_reason = str(exc)
                utils.logger.warning(
                    f"[TaobaoClient] 商品 {item_id} 第 {page_number} 页触发淘宝风控，"
                    f"已安全保留 {len(comments)} 条评论，停止继续请求"
                )
                break

            if response.get("code") != "SUCCESS":
                message = response.get("message") or "未知错误"
                error = TaobaoDataFetchError(f"淘宝评论接口拒绝请求：{message}")
                if self._is_risk_control_error(error):
                    self.last_stop_reason = str(error)
                    utils.logger.warning(
                        f"[TaobaoClient] 商品 {item_id} 第 {page_number} 页触发淘宝风控，"
                        f"已安全保留 {len(comments)} 条评论，停止继续请求"
                    )
                    break
                raise error

            page_comments = response.get("commentList")
            if not isinstance(page_comments, list):
                raise TaobaoDataFetchError("淘宝评论列表格式异常")
            remaining_count = max_count - len(comments)
            page_comments = page_comments[:remaining_count]
            if callback and page_comments:
                await callback(item_id, page_comments)
            comments.extend(page_comments)

            if (
                not page_comments
                or not response.get("hasNext")
                or len(comments) >= max_count
            ):
                break

            page_number += 1

        return comments[:max_count]
