# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import asyncio
import random
from functools import wraps
from typing import Any, Awaitable, Callable

import config
from tools import utils


CommentCallback = Callable[..., Awaitable[Any]]


class CommentCrawlThrottle:
    """Serialize comment persistence and apply configured random delays."""

    def __init__(self) -> None:
        self.comment_interval = (
            config.COMMENT_INTERVAL_MIN,
            config.COMMENT_INTERVAL_MAX,
        )
        self.page_interval = (config.PAGE_INTERVAL_MIN, config.PAGE_INTERVAL_MAX)
        self.periodic_page_count = config.PERIODIC_PAUSE_PAGE_COUNT
        self.periodic_pause = (
            config.PERIODIC_PAUSE_MIN,
            config.PERIODIC_PAUSE_MAX,
        )
        self.completed_pages = 0
        self._lock = asyncio.Lock()

    async def process_page(
        self,
        callback: CommentCallback,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if not args or not isinstance(args[-1], list):
            raise TypeError("comment callback must receive a comment list as its last argument")

        comments = args[-1]
        prefix_args = args[:-1]
        result = None

        async with self._lock:
            for index, comment in enumerate(comments):
                result = await callback(*prefix_args, [comment], **kwargs)
                if index + 1 < len(comments):
                    await self._wait(self.comment_interval, "单条评论间隔")

            self.completed_pages += 1
            if self.completed_pages % self.periodic_page_count == 0:
                await self._wait(
                    self.periodic_pause,
                    f"已完成 {self.completed_pages} 页，周期休息",
                )
            else:
                await self._wait(
                    self.page_interval,
                    f"已完成第 {self.completed_pages} 页，分页间隔",
                )

        return result

    @staticmethod
    async def _wait(interval: tuple[float, float], reason: str) -> None:
        minimum, maximum = interval
        if maximum <= 0:
            return
        delay = random.uniform(minimum, maximum)
        utils.logger.info(f"[CommentCrawlThrottle] {reason} {delay:.1f} 秒")
        await asyncio.sleep(delay)


def create_comment_page_callback(callback: CommentCallback) -> CommentCallback:
    """Wrap a page callback so every comment is stored and paced individually."""

    throttle = CommentCrawlThrottle()

    @wraps(callback)
    async def throttled_callback(*args: Any, **kwargs: Any) -> Any:
        return await throttle.process_page(callback, *args, **kwargs)

    return throttled_callback


__all__ = ["CommentCrawlThrottle", "create_comment_page_callback"]
