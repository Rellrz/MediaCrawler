# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import asyncio
from typing import Any, Dict, List
from urllib.parse import urlparse

from playwright.async_api import Page


class JdDataFetchError(RuntimeError):
    """Raised when JD rejects or cannot complete a comment request."""


class JdClient:
    PAGE_SIZE = 10
    COMMENT_API_BY_HOST = {
        "item.jd.com": "https://api.m.jd.com",
        "item.jingdonghealth.cn": "https://api.jingdonghealth.cn",
    }

    def __init__(self, page: Page) -> None:
        self.page = page

    async def get_comment_page(self, sku_id: str, page_number: int) -> Dict[str, Any]:
        """Fetch one signed comment page from the current JD product page."""
        page_hostname = urlparse(self.page.url).hostname
        api_base_url = self.COMMENT_API_BY_HOST.get(page_hostname or "")
        if not api_base_url:
            raise JdDataFetchError(f"不支持的京东商品页域名：{page_hostname or 'unknown'}")

        response = await self.page.evaluate(
            """
            async ({skuId, pageNumber, pageSize, apiBaseUrl, requireDeviceToken}) => {
                if (typeof window.ParamsSign !== "function" ||
                    typeof window.SHA256 !== "function") {
                    throw new Error("京东请求签名环境未加载");
                }

                const waitForFunction = async (name, timeoutMs) => {
                    const deadline = Date.now() + timeoutMs;
                    while (Date.now() < deadline) {
                        if (typeof window[name] === "function") return true;
                        await new Promise((resolve) => setTimeout(resolve, 200));
                    }
                    return false;
                };
                const hasJsToken = await waitForFunction("getJsToken", 5000);
                if (requireDeviceToken && !hasJsToken) {
                    throw new Error("京东健康设备令牌组件 getJsToken 未加载");
                }

                let eidToken = "";
                if (hasJsToken) {
                    eidToken = await new Promise((resolve) => {
                        let completed = false;
                        const finish = (value) => {
                            if (completed) return;
                            completed = true;
                            clearTimeout(timer);
                            resolve(value || "");
                        };
                        const timer = setTimeout(() => finish(""), 5000);
                        try {
                            const tokenResult = window.getJsToken(
                                (result) => finish(result?.jsToken || ""),
                                3000
                            );
                            if (typeof tokenResult === "string") {
                                finish(tokenResult);
                            } else if (tokenResult?.then) {
                                tokenResult
                                    .then((result) => finish(result?.jsToken || result || ""))
                                    .catch(() => finish(""));
                            }
                        } catch (error) {
                            finish("");
                        }
                    });
                }
                if (requireDeviceToken && !eidToken) {
                    throw new Error("京东健康设备令牌 x-api-eid-token 获取失败");
                }

                const product = window.pageConfig?.product || {};
                const category = Array.isArray(product.cat)
                    ? product.cat.join(",")
                    : String(product.cat || "");
                const body = {
                    requestSource: "pc",
                    shopComment: 0,
                    sameComment: 0,
                    channel: null,
                    extInfo: {
                        isQzc: "0",
                        spuId: skuId,
                        commentRate: "1",
                        needTopAlbum: "1",
                        bbtf: ""
                    },
                    sku: skuId,
                    category,
                    num: String(pageSize),
                    pageSize: String(pageSize),
                    pictureCommentType: "A",
                    scval: null,
                    shadowMainSku: "0",
                    shieldCurrentComment: "1",
                    type: "0",
                    isFirstRequest: false,
                    style: "0",
                    isCurrentSku: true,
                    sortType: "5",
                    tagId: "",
                    tagType: "",
                    pageNum: String(pageNumber),
                    shopType: String(product.shopType || "0"),
                    shopId: String(product.shopId || "")
                };
                const bodyText = JSON.stringify(body);
                const cookies = Object.fromEntries(
                    document.cookie.split(";").map((item) => {
                        const [key, ...valueParts] = item.trim().split("=");
                        return [key, valueParts.join("=")];
                    })
                );
                const uuid = (cookies.__jda || "").split(".")[1] || "";
                const params = {
                    appid: "pc-rate-qa",
                    functionId: "getCommentListPage",
                    client: "pc",
                    clientVersion: "1.0.0",
                    loginType: "3",
                    t: Date.now(),
                    uuid,
                    body: bodyText
                };
                if (eidToken) {
                    params["x-api-eid-token"] = eidToken;
                }
                const signature = await new window.ParamsSign({
                    appId: "01a47",
                    debug: false
                }).sign({
                    functionId: params.functionId,
                    appid: params.appid,
                    client: params.client,
                    clientVersion: params.clientVersion,
                    t: params.t,
                    body: window.SHA256(bodyText)
                });
                if (!signature?.h5st) {
                    throw new Error("京东评论请求签名失败");
                }
                params.h5st = signature.h5st;

                const apiUrl = `${apiBaseUrl}/client.action`;
                const result = await fetch(apiUrl, {
                    method: "POST",
                    credentials: "include",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
                    },
                    body: new URLSearchParams(params).toString()
                });
                if (!result.ok) {
                    const responseText = (await result.text()).slice(0, 500);
                    const requestId = result.headers.get("x-api-request-id") || "unknown";
                    throw new Error(
                        `${apiUrl} 返回 HTTP ${result.status}; ` +
                        `requestId=${requestId}; response=${responseText || "empty"}`
                    );
                }
                return await result.json();
            }
            """,
            {
                "skuId": sku_id,
                "pageNumber": page_number,
                "pageSize": self.PAGE_SIZE,
                "apiBaseUrl": api_base_url,
                "requireDeviceToken": page_hostname == "item.jingdonghealth.cn",
            },
        )
        if not isinstance(response, dict):
            raise JdDataFetchError("京东评论接口返回了无法识别的数据")
        if str(response.get("code")) != "0":
            return response

        result = response.get("result")
        if not isinstance(result, dict):
            raise JdDataFetchError("京东评论接口缺少 result 数据")
        page_info = result.get("pageInfo") or {}
        page_data = page_info.get("data") or {}
        floors = result.get("floors") or []
        list_floor = next(
            (
                floor
                for floor in floors
                if isinstance(floor, dict) and floor.get("mId") == "commentlist-list"
            ),
            {},
        )
        floor_items = list_floor.get("data") or []
        comments = [
            item["commentInfo"]
            for item in floor_items
            if isinstance(item, dict) and isinstance(item.get("commentInfo"), dict)
        ]
        return {
            "code": response.get("code"),
            "message": response.get("message") or response.get("msg"),
            "maxPage": page_data.get("maxPage", 0),
            "commentInfoList": comments,
        }

    async def get_comments(self, sku_id: str, max_count: int) -> List[Dict[str, Any]]:
        """Fetch at most ``max_count`` comments, following JD pagination."""
        if max_count <= 0:
            return []

        comments: List[Dict[str, Any]] = []
        page_number = 1
        while len(comments) < max_count:
            try:
                response = await self.get_comment_page(sku_id, page_number)
            except JdDataFetchError:
                raise
            except Exception as exc:
                raise JdDataFetchError(f"京东评论请求失败：{exc}") from exc

            if str(response.get("code")) != "0":
                message = response.get("message") or response.get("msg") or "未知错误"
                raise JdDataFetchError(f"京东评论接口拒绝请求：{message}")

            page_comments = response.get("commentInfoList") or []
            if not isinstance(page_comments, list):
                raise JdDataFetchError("京东评论列表格式异常")
            comments.extend(item for item in page_comments if isinstance(item, dict))

            max_page = int(response.get("maxPage") or page_number)
            if not page_comments or page_number >= max_page:
                break
            page_number += 1
            await asyncio.sleep(1)

        return comments[:max_count]
