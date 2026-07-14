# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import asyncio

import pytest

from media_platform.taobao.client import TaobaoClient, TaobaoDataFetchError
from media_platform.taobao.help import parse_taobao_product_url


class FakePage:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.scripts = []

    async def evaluate(self, script, arguments):
        self.scripts.append(script)
        self.calls.append(arguments)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def comment_response(start: int, has_next: bool = True):
    return {
        "ret": ["SUCCESS::调用成功"],
        "data": {
            "module": {
                "hasNext": str(has_next).lower(),
                "reviewVOList": [
                    {
                        "id": str(index),
                        "reviewWordContent": f"评论 {index}",
                        "reviewDate": "2026-07-14",
                        "userNick": f"用户 {index}",
                        "headPicUrl": "https://img.example/avatar.jpg",
                        "skuText": {"颜色": "黑色", "尺码": "M"},
                        "reviewPicPathList": ["https://img.example/review.jpg"],
                        "interactionVO": {"likeCount": "2"},
                        "reviewAppendVO": {
                            "intervalDay": "3",
                            "appendedWordContent": "追评",
                            "reviewPicPathList": [],
                        },
                    }
                    for index in range(start, start + 20)
                ],
            }
        },
    }


def test_parse_standard_taobao_product_url():
    product = parse_taobao_product_url(
        "https://item.taobao.com/item.htm?id=752598787556&utm_source=test"
    )

    assert product.item_id == "752598787556"
    assert product.url.startswith("https://item.taobao.com/item.htm")
    assert product.biz_code == "ali.china.taobao"


def test_parse_tmall_product_url_with_tracking_parameters():
    product = parse_taobao_product_url(
        "https://detail.tmall.com/item.htm?"
        "ali_refid=a3_420860_1007%3A35175454%3AH%3A35175454_0_24117896519"
        "&ali_trackid=319_06c8e16d33cf61295ba61d78b62d1518"
        "&id=703832297172&item_type=ad&skuId=4953145268754"
    )

    assert product.item_id == "703832297172"
    assert product.biz_code == "ali.china.tmall"


@pytest.mark.parametrize(
    "url",
    [
        "752598787556",
        "http://item.taobao.com/item.htm?id=752598787556",
        "https://detail.tmall.com/detail.htm?id=752598787556",
        "https://item.taobao.com/item.htm",
        "https://item.taobao.com/item.htm?id=not-a-number",
    ],
)
def test_reject_non_standard_taobao_product_url(url):
    with pytest.raises(ValueError, match="标准淘宝或天猫商品链接"):
        parse_taobao_product_url(url)


def test_current_pc_review_api_and_response_are_used():
    page = FakePage([comment_response(1, has_next=False)])

    response = asyncio.run(
        TaobaoClient(page).get_comment_page(
            "752598787556", "ali.china.taobao", 3
        )
    )

    assert page.calls[0] == {
        "itemId": "752598787556",
        "bizCode": "ali.china.taobao",
        "pageNumber": 3,
        "pageSize": 20,
    }
    assert "mtop.alibaba.review.list.for.new.pc.detail" in page.scripts[0]
    assert "bizCode," in page.scripts[0]
    assert "error.ret" in page.scripts[0]
    assert response["code"] == "SUCCESS"
    assert response["hasNext"] is False
    assert response["commentList"][0]["comment_id"] == "1"
    assert response["commentList"][0]["sku_info"] == "黑色 / M"


def test_comment_pagination_starts_at_requested_page(monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    page = FakePage(
        [
            comment_response(241),
            comment_response(261, has_next=False),
        ]
    )

    comments = asyncio.run(
        TaobaoClient(page).get_comments(
            "123", "ali.china.tmall", 40, 13
        )
    )

    assert len(comments) == 40
    assert [call["pageNumber"] for call in page.calls] == [13, 14]
    assert all(call["bizCode"] == "ali.china.tmall" for call in page.calls)


def test_risk_control_keeps_comments_already_stored(monkeypatch):
    async def no_sleep(_):
        return None

    stored_comments = []

    async def store_comments(item_id, comments):
        for comment in comments:
            stored_comments.append((item_id, comment["comment_id"]))

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    page = FakePage(
        [
            comment_response(1),
            {"ret": ["FAIL_SYS_USER_VALIDATE::哨兵验证"], "data": {}},
        ]
    )
    client = TaobaoClient(page)

    comments = asyncio.run(
        client.get_comments(
            "123",
            "ali.china.taobao",
            40,
            1,
            callback=store_comments,
        )
    )

    assert len(comments) == 20
    assert stored_comments == [("123", str(index)) for index in range(1, 21)]
    assert "FAIL_SYS_USER_VALIDATE" in client.last_stop_reason


def test_missing_comment_id_is_rejected():
    response = comment_response(1, has_next=False)
    response["data"]["module"]["reviewVOList"] = [{}]
    page = FakePage([response])

    with pytest.raises(TaobaoDataFetchError, match="评论 ID"):
        asyncio.run(
            TaobaoClient(page).get_comment_page(
                "123", "ali.china.taobao", 1
            )
        )
