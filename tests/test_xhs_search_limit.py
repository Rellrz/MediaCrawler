# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import asyncio
from unittest.mock import AsyncMock

import pytest

import config
from media_platform.xhs import core as xhs_core
from media_platform.kuaishou import core as kuaishou_core


@pytest.mark.asyncio
@pytest.mark.parametrize(("max_count", "expected_pages"), [(1, 1), (20, 1), (21, 2)])
async def test_search_stops_at_requested_count(monkeypatch, max_count, expected_pages):
    crawler = xhs_core.XiaoHongShuCrawler()

    async def search_page(**kwargs):
        page = kwargs["page"]
        return {
            "items": [
                {
                    "id": f"note-{page}-{index}",
                    "xsec_source": "pc_search",
                    "xsec_token": f"token-{page}-{index}",
                    "model_type": "note",
                }
                for index in range(20)
            ],
            "has_more": page < expected_pages,
        }

    async def note_detail(**kwargs):
        return {
            "note_id": kwargs["note_id"],
            "xsec_token": kwargs["xsec_token"],
        }

    crawler.xhs_client = AsyncMock()
    crawler.xhs_client.get_note_by_keyword.side_effect = search_page
    crawler.get_note_detail_async_task = AsyncMock(side_effect=note_detail)
    crawler.get_notice_media = AsyncMock()
    crawler.batch_get_note_comments = AsyncMock()
    update_note = AsyncMock()

    monkeypatch.setattr(config, "CRAWLER_MAX_NOTES_COUNT", max_count)
    monkeypatch.setattr(config, "KEYWORDS", "test")
    monkeypatch.setattr(config, "START_PAGE", 1)
    monkeypatch.setattr(config, "CRAWLER_MAX_SLEEP_SEC", 0)
    monkeypatch.setattr(xhs_core.xhs_store, "update_xhs_note", update_note)

    await crawler.search()

    assert update_note.await_count == max_count
    assert crawler.xhs_client.get_note_by_keyword.await_count == expected_pages
    assert config.CRAWLER_MAX_NOTES_COUNT == max_count


@pytest.mark.asyncio
async def test_kuaishou_search_stops_on_empty_response(monkeypatch):
    crawler = kuaishou_core.KuaishouCrawler()
    crawler.ks_client = AsyncMock()
    crawler.ks_client.search_info_by_keyword.return_value = None

    monkeypatch.setattr(config, "CRAWLER_MAX_NOTES_COUNT", 21)
    monkeypatch.setattr(config, "KEYWORDS", "test")
    monkeypatch.setattr(config, "START_PAGE", 1)

    await asyncio.wait_for(crawler.search(), timeout=1)

    crawler.ks_client.search_info_by_keyword.assert_awaited_once()
