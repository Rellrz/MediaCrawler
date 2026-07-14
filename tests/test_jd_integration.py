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
from media_platform.jd import core as jd_core
from media_platform.jd.core import JdCrawler
from store.jd import JdStoreFactory, _normalize_comment


def build_request(max_comments_count: int = 35) -> CrawlerStartRequest:
    return CrawlerStartRequest(
        platform="jd",
        crawler_type="detail",
        specified_ids="https://item.jd.com/100012043978.html",
        max_notes_count=1,
        max_comments_count=max_comments_count,
    )


def test_jd_crawler_is_registered():
    assert type(CrawlerFactory.create_crawler("jd")).__name__ == "JdCrawler"


def test_api_command_passes_product_url_and_comment_count():
    command = CrawlerManager()._build_command(build_request())

    specified_index = command.index("--specified_id")
    count_index = command.index("--max_comments_count_singlenotes")
    assert command[specified_index + 1] == "https://item.jd.com/100012043978.html"
    assert command[count_index + 1] == "35"


def test_cli_sets_jd_product_urls_and_comment_count(monkeypatch):
    monkeypatch.setattr(config, "JD_SPECIFIED_PRODUCT_URL_LIST", [])
    result = asyncio.run(
        parse_cmd(
            [
                "--platform",
                "jd",
                "--type",
                "detail",
                "--specified_id",
                "https://item.jd.com/100012043978.html",
                "--max_comments_count_singlenotes",
                "35",
            ]
        )
    )

    assert config.JD_SPECIFIED_PRODUCT_URL_LIST == [
        "https://item.jd.com/100012043978.html"
    ]
    assert result.max_comments_count_singlenotes == 35


def test_jd_store_rejects_database_output(monkeypatch):
    monkeypatch.setattr(config, "SAVE_DATA_OPTION", "db")

    with pytest.raises(ValueError, match="csv、json、jsonl 或 excel"):
        JdStoreFactory.create_store()


def test_jd_comment_normalization_keeps_key_fields():
    normalized = _normalize_comment(
        "100012043978",
        {
            "guid": "comment-1",
            "commentData": "商品很好",
            "score": 5,
            "userNickName": "测试用户",
            "pictureInfoList": [{"picURL": "https://img.example/1.jpg"}],
        },
    )

    assert normalized["sku_id"] == "100012043978"
    assert normalized["comment_id"] == "comment-1"
    assert normalized["content"] == "商品很好"
    assert normalized["pictures"] == "https://img.example/1.jpg"


def test_jd_cdp_mode_uses_cdp_browser_manager(monkeypatch):
    browser_context = object()

    class FakeCdpManager:
        def __init__(self):
            self.launch_args = None

        async def launch_and_connect(self, **kwargs):
            self.launch_args = kwargs
            return browser_context

        async def get_browser_info(self):
            return {"is_connected": True}

        async def cleanup(self):
            return None

    monkeypatch.setattr(jd_core, "CDPBrowserManager", FakeCdpManager)
    crawler = JdCrawler()
    playwright = object()

    result = asyncio.run(
        crawler.launch_browser_with_cdp(
            playwright, None, "test-agent", headless=False
        )
    )

    assert result is browser_context
    assert crawler.cdp_manager is not None
    assert crawler.cdp_manager.launch_args["playwright"] is playwright
    assert crawler.cdp_manager.launch_args["user_agent"] == "test-agent"


def test_jd_close_uses_cdp_manager_cleanup():
    class FakeCdpManager:
        def __init__(self):
            self.cleaned = False

        async def cleanup(self):
            self.cleaned = True

    crawler = JdCrawler()
    manager = FakeCdpManager()
    crawler.cdp_manager = manager

    asyncio.run(crawler.close())

    assert manager.cleaned is True
    assert crawler.cdp_manager is None
