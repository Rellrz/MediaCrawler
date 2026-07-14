# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import asyncio

import pytest

from media_platform.jd.client import JdClient, JdDataFetchError
from media_platform.jd.core import JdCrawler
from media_platform.jd.help import parse_jd_product_url
from playwright.async_api import Error as PlaywrightError


class FakePage:
    def __init__(self, responses, url="https://item.jd.com/100012043978.html"):
        self.responses = list(responses)
        self.calls = []
        self.scripts = []
        self.url = url

    async def evaluate(self, script, arguments):
        self.scripts.append(script)
        self.calls.append(arguments)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def comment_response(start: int, max_page: int = 3):
    return {
        "code": "0",
        "result": {
            "pageInfo": {"data": {"maxPage": str(max_page)}},
            "floors": [
                {
                    "mId": "commentlist-list",
                    "data": [
                        {"commentInfo": {"guid": str(index)}}
                        for index in range(start, start + 10)
                    ],
                }
            ],
        },
    }


def test_parse_standard_jd_product_url():
    product = parse_jd_product_url(
        "https://item.jd.com/100012043978.html?utm_source=test"
    )

    assert product.sku_id == "100012043978"


def test_parse_jingdong_health_product_url():
    product = parse_jd_product_url(
        "https://item.jingdonghealth.cn/2943746.html"
    )

    assert product.sku_id == "2943746"
    assert product.url == "https://item.jingdonghealth.cn/2943746.html"


@pytest.mark.parametrize(
    "url",
    [
        "https://u.jd.com/short-link",
        "https://item.m.jd.com/product/100012043978.html",
        "https://example.com/2943746.html",
        "100012043978",
        "https://item.jd.com/not-a-sku.html",
    ],
)
def test_reject_non_standard_jd_product_url(url):
    with pytest.raises(ValueError, match="标准京东商品链接"):
        parse_jd_product_url(url)


def test_comment_pagination_stops_at_requested_count(monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    page = FakePage(
        [
            comment_response(0),
            comment_response(10),
        ]
    )

    comments = asyncio.run(JdClient(page).get_comments("123", 15))

    assert len(comments) == 15
    assert [call["pageNumber"] for call in page.calls] == [1, 2]


def test_comment_api_error_is_reported():
    page = FakePage([{"code": "3", "message": "需要验证"}])

    with pytest.raises(JdDataFetchError, match="需要验证"):
        asyncio.run(JdClient(page).get_comments("123", 10))


def test_standard_jd_page_uses_standard_comment_api():
    page = FakePage([comment_response(0, max_page=1)])

    asyncio.run(JdClient(page).get_comment_page("100012043978", 1))

    assert page.calls[0]["apiBaseUrl"] == "https://api.m.jd.com"
    assert page.calls[0]["requireDeviceToken"] is False


def test_jingdong_health_page_uses_health_comment_api():
    page = FakePage(
        [comment_response(0, max_page=1)],
        url="https://item.jingdonghealth.cn/2943746.html",
    )

    asyncio.run(JdClient(page).get_comment_page("2943746", 1))

    assert page.calls[0]["apiBaseUrl"] == "https://api.jingdonghealth.cn"
    assert page.calls[0]["requireDeviceToken"] is True
    assert 'params["x-api-eid-token"] = eidToken' in page.scripts[0]
    assert 'result.headers.get("x-api-request-id")' in page.scripts[0]


def test_unknown_jd_page_domain_is_rejected():
    page = FakePage([], url="https://example.com/2943746.html")

    with pytest.raises(JdDataFetchError, match="example.com"):
        asyncio.run(JdClient(page).get_comment_page("2943746", 1))


def test_http_error_keeps_api_domain_and_status():
    page = FakePage(
        [RuntimeError("https://api.jingdonghealth.cn/client.action 返回 HTTP 403")],
        url="https://item.jingdonghealth.cn/2943746.html",
    )

    with pytest.raises(
        JdDataFetchError, match=r"api\.jingdonghealth\.cn.*HTTP 403"
    ):
        asyncio.run(JdClient(page).get_comments("2943746", 10))


def test_product_page_load_error_has_actionable_message():
    class FailedPage:
        async def goto(self, *args, **kwargs):
            raise PlaywrightError("timeout")

    crawler = JdCrawler()
    crawler.context_page = FailedPage()

    with pytest.raises(JdDataFetchError, match="登录状态.*验证码"):
        asyncio.run(
            crawler._open_product_page("https://item.jd.com/100012043978.html")
        )
