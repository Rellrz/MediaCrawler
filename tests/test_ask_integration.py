# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import asyncio
from pathlib import Path

import config
import pytest
from api.main import get_platforms
from api.schemas.crawler import CrawlerStartRequest
from api.services.crawler_manager import CrawlerManager
from cmd_arg.arg import parse_cmd
from main import CrawlerFactory
from media_platform.ask import core as ask_core
from media_platform.ask.core import AskCrawler


def build_request() -> CrawlerStartRequest:
    return CrawlerStartRequest(
        platform="ask",
        crawler_type="search",
        keywords="小儿七星茶",
        start_page=3,
        max_notes_count=20,
        max_comments_count=4,
    )


def test_ask_crawler_is_registered():
    assert type(CrawlerFactory.create_crawler("ask")).__name__ == "AskCrawler"


def test_api_command_passes_search_configuration():
    command = CrawlerManager()._build_command(build_request())

    assert command[command.index("--platform") + 1] == "ask"
    assert command[command.index("--keywords") + 1] == "小儿七星茶"
    assert command[command.index("--start") + 1] == "3"
    assert command[command.index("--max_notes_count") + 1] == "20"
    assert command[command.index("--max_comments_count_singlenotes") + 1] == "4"


def test_cli_sets_ask_search_configuration():
    result = asyncio.run(
        parse_cmd(
            [
                "--platform",
                "ask",
                "--type",
                "search",
                "--keywords",
                "小儿七星茶",
                "--start",
                "3",
                "--max_notes_count",
                "20",
                "--max_comments_count_singlenotes",
                "4",
            ]
        )
    )

    assert result.platform == "ask"
    assert config.KEYWORDS == "小儿七星茶"
    assert config.START_PAGE == 3
    assert config.CRAWLER_MAX_NOTES_COUNT == 20
    assert config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES == 4


def test_api_platform_list_contains_120ask():
    result = asyncio.run(get_platforms())

    assert {
        "value": "ask",
        "label": "有问必答 (120ask)",
        "icon": "stethoscope",
    } in result["platforms"]


def test_webui_locks_120ask_to_search_mode():
    asset = Path("api/webui/assets/index-DvClRayq.js").read_text(encoding="utf-8")

    assert 'b==="ask"?"search"' in asset
    assert 'e.platform==="ask"&&e.crawler_type==="search"' in asset
    assert 'askMaxAnswers:"每个问题医生回复数量"' in asset
    assert '!e.enable_comments||e.platform==="ask"' in asset


def test_ask_cdp_mode_uses_shared_browser_manager(monkeypatch):
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

    monkeypatch.setattr(ask_core, "CDPBrowserManager", FakeCdpManager)
    crawler = AskCrawler()
    playwright = object()

    result = asyncio.run(
        crawler.launch_browser_with_cdp(
            playwright,
            None,
            "test-agent",
            headless=False,
        )
    )

    assert result is browser_context
    assert crawler.cdp_manager.launch_args["playwright"] is playwright
    assert crawler.cdp_manager.launch_args["user_agent"] == "test-agent"


def test_ask_close_uses_cdp_cleanup():
    class FakeCdpManager:
        def __init__(self):
            self.cleaned = False

        async def cleanup(self):
            self.cleaned = True

    crawler = AskCrawler()
    manager = FakeCdpManager()
    crawler.cdp_manager = manager

    asyncio.run(crawler.close())

    assert manager.cleaned is True
    assert crawler.cdp_manager is None


def test_ask_rejects_non_search_mode(monkeypatch):
    monkeypatch.setattr(config, "CRAWLER_TYPE", "detail")
    crawler = AskCrawler()

    with pytest.raises(ValueError, match="仅支持 search 模式"):
        asyncio.run(crawler.start())
