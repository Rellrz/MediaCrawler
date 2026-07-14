# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import asyncio

import pytest

import config
from api.schemas.crawler import CrawlerStartRequest
from api.services.crawler_manager import CrawlerManager
from cmd_arg.arg import parse_cmd
from main import CrawlerFactory
from store import taobao as taobao_store
from store.taobao import TaobaoStoreFactory, _normalize_comment


def build_request(max_comments_count: int = 35) -> CrawlerStartRequest:
    return CrawlerStartRequest(
        platform="tb",
        crawler_type="detail",
        specified_ids="https://detail.tmall.com/item.htm?id=703832297172",
        max_notes_count=1,
        max_comments_count=max_comments_count,
    )


def test_taobao_crawler_is_registered():
    assert type(CrawlerFactory.create_crawler("tb")).__name__ == "TaobaoCrawler"


def test_api_command_passes_product_url_and_comment_count():
    command = CrawlerManager()._build_command(build_request())

    specified_index = command.index("--specified_id")
    count_index = command.index("--max_comments_count_singlenotes")
    assert command[specified_index + 1] == (
        "https://detail.tmall.com/item.htm?id=703832297172"
    )
    assert command[count_index + 1] == "35"


def test_cli_sets_taobao_product_urls_and_comment_count(monkeypatch):
    monkeypatch.setattr(config, "TB_SPECIFIED_PRODUCT_URL_LIST", [])
    result = asyncio.run(
        parse_cmd(
            [
                "--platform",
                "tb",
                "--type",
                "detail",
                "--specified_id",
                "https://detail.tmall.com/item.htm?id=703832297172",
                "--max_comments_count_singlenotes",
                "35",
            ]
        )
    )

    assert config.TB_SPECIFIED_PRODUCT_URL_LIST == [
        "https://detail.tmall.com/item.htm?id=703832297172"
    ]
    assert result.max_comments_count_singlenotes == 35


def test_taobao_store_rejects_database_output(monkeypatch):
    monkeypatch.setattr(config, "SAVE_DATA_OPTION", "db")

    with pytest.raises(ValueError, match="csv、json、jsonl 或 excel"):
        TaobaoStoreFactory.create_store()


def test_taobao_comment_normalization_keeps_key_fields():
    normalized = _normalize_comment(
        "752598787556",
        {
            "comment_id": "comment-1",
            "content": "商品很好",
            "nickname": "测试用户",
            "sku_info": "黑色 / M",
            "pictures": ["https://img.example/1.jpg"],
        },
    )

    assert normalized["item_id"] == "752598787556"
    assert normalized["comment_id"] == "comment-1"
    assert normalized["content"] == "商品很好"
    assert normalized["pictures"] == "https://img.example/1.jpg"


def test_taobao_store_writes_comments_one_by_one(monkeypatch):
    stored_ids = []

    class FakeStore:
        async def store_comment(self, comment):
            stored_ids.append(comment["comment_id"])
            if comment["comment_id"] == "2":
                raise RuntimeError("disk full")

    monkeypatch.setattr(
        taobao_store.TaobaoStoreFactory,
        "create_store",
        staticmethod(lambda: FakeStore()),
    )

    with pytest.raises(RuntimeError, match="disk full"):
        asyncio.run(
            taobao_store.batch_update_taobao_comments(
                "123",
                [
                    {"comment_id": "1", "pictures": []},
                    {"comment_id": "2", "pictures": []},
                    {"comment_id": "3", "pictures": []},
                ],
            )
        )

    assert stored_ids == ["1", "2"]
