# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import pytest

from media_platform.bilibili.client import BilibiliClient


@pytest.mark.asyncio
async def test_root_comments_are_stored_before_sub_comment_request_fails():
    client = BilibiliClient.__new__(BilibiliClient)

    async def get_video_comments(*_args, **_kwargs):
        return {
            "cursor": {"is_end": True, "next": 0},
            "replies": [{"rpid": 1, "rcount": 1}],
        }

    async def fail_to_get_sub_comments(*_args, **_kwargs):
        raise RuntimeError("sub-comment request failed")

    stored_comments = []

    async def store_comments(video_id, comments):
        for comment in comments:
            stored_comments.append((video_id, comment["rpid"]))

    client.get_video_comments = get_video_comments
    client.get_video_all_level_two_comments = fail_to_get_sub_comments

    with pytest.raises(RuntimeError, match="sub-comment request failed"):
        await client.get_video_all_comments(
            "BV1test",
            crawl_interval=0,
            is_fetch_sub_comments=True,
            callback=store_comments,
            max_count=10,
        )

    assert stored_comments == [("BV1test", 1)]
