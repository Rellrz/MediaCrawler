# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import asyncio
from pathlib import Path

import pytest

import config
from tools.comment_crawl_throttle import (
    CommentCrawlThrottle,
    create_comment_page_callback,
)


def configure_speed(monkeypatch):
    monkeypatch.setattr(config, "COMMENT_INTERVAL_MIN", 0.5)
    monkeypatch.setattr(config, "COMMENT_INTERVAL_MAX", 1.5)
    monkeypatch.setattr(config, "PAGE_INTERVAL_MIN", 2.0)
    monkeypatch.setattr(config, "PAGE_INTERVAL_MAX", 4.0)
    monkeypatch.setattr(config, "PERIODIC_PAUSE_PAGE_COUNT", 2)
    monkeypatch.setattr(config, "PERIODIC_PAUSE_MIN", 10.0)
    monkeypatch.setattr(config, "PERIODIC_PAUSE_MAX", 20.0)


def test_comments_are_stored_one_by_one_with_page_delays(monkeypatch):
    configure_speed(monkeypatch)
    sleeps = []
    batches = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    async def store_comments(note_id, comments):
        batches.append((note_id, comments))

    monkeypatch.setattr(
        "tools.comment_crawl_throttle.random.uniform", lambda minimum, maximum: minimum
    )
    monkeypatch.setattr("tools.comment_crawl_throttle.asyncio.sleep", fake_sleep)
    callback = create_comment_page_callback(store_comments)

    async def run_pages():
        await callback("note-1", [{"id": "1"}, {"id": "2"}])
        await callback("note-1", [{"id": "3"}])

    asyncio.run(run_pages())

    assert batches == [
        ("note-1", [{"id": "1"}]),
        ("note-1", [{"id": "2"}]),
        ("note-1", [{"id": "3"}]),
    ]
    assert sleeps == [0.5, 2.0, 10.0]


def test_storage_failure_keeps_previous_comment_and_stops_waiting(monkeypatch):
    configure_speed(monkeypatch)
    stored_ids = []
    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    async def store_comments(comments):
        comment_id = comments[0]["id"]
        stored_ids.append(comment_id)
        if comment_id == "2":
            raise RuntimeError("disk full")

    monkeypatch.setattr("tools.comment_crawl_throttle.asyncio.sleep", fake_sleep)
    throttle = CommentCrawlThrottle()

    with pytest.raises(RuntimeError, match="disk full"):
        asyncio.run(
            throttle.process_page(
                store_comments,
                [{"id": "1"}, {"id": "2"}, {"id": "3"}],
            )
        )

    assert stored_ids == ["1", "2"]
    assert throttle.completed_pages == 0


def test_store_comments_and_finish_page_are_independent(monkeypatch):
    configure_speed(monkeypatch)
    stored_ids = []
    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    async def store_comments(question_id, comments):
        stored_ids.append((question_id, comments[0]["id"]))

    monkeypatch.setattr(
        "tools.comment_crawl_throttle.random.uniform",
        lambda minimum, maximum: minimum,
    )
    monkeypatch.setattr("tools.comment_crawl_throttle.asyncio.sleep", fake_sleep)
    throttle = CommentCrawlThrottle()

    async def run():
        await throttle.store_comments(
            store_comments,
            "question-1",
            [{"id": "1"}, {"id": "2"}],
        )
        assert throttle.completed_pages == 0
        await throttle.wait_between_items()
        await throttle.finish_page()

    asyncio.run(run())

    assert stored_ids == [("question-1", "1"), ("question-1", "2")]
    assert throttle.completed_pages == 1
    assert sleeps == [0.5, 0.5, 2.0]


def test_callback_requires_comment_list_as_last_argument(monkeypatch):
    configure_speed(monkeypatch)

    async def callback(value):
        return value

    with pytest.raises(TypeError, match="comment list"):
        asyncio.run(CommentCrawlThrottle().process_page(callback, "invalid"))


@pytest.mark.parametrize(
    "platform",
    ["xhs", "douyin", "kuaishou", "bilibili", "weibo", "tieba", "zhihu", "jd", "taobao"],
)
def test_all_platforms_use_shared_comment_throttle(platform):
    source = (Path("media_platform") / platform / "core.py").read_text(
        encoding="utf-8"
    )

    assert "from tools.comment_crawl_throttle import create_comment_page_callback" in source
    assert "callback=create_comment_page_callback(" in source
