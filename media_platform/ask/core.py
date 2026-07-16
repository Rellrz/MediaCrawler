# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import os
from typing import Dict, Optional

from playwright.async_api import (
    BrowserContext,
    BrowserType,
    Page,
    Playwright,
    async_playwright,
)

import config
from base.base_crawler import AbstractCrawler
from tools import utils
from tools.cdp_browser import CDPBrowserManager
from tools.comment_crawl_throttle import CommentCrawlThrottle
from var import crawler_type_var, source_keyword_var

from .client import AskClient


class AskCrawler(AbstractCrawler):
    cdp_manager: Optional[CDPBrowserManager]

    def __init__(self) -> None:
        self.browser_context: BrowserContext
        self.context_page: Page
        self.cdp_manager = None
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )

    async def start(self) -> None:
        if config.CRAWLER_TYPE != "search":
            raise ValueError("120ask 平台当前仅支持 search 模式")
        keywords = [item.strip() for item in config.KEYWORDS.split(",") if item.strip()]
        if not keywords:
            raise ValueError("请至少提供一个 120ask 搜索关键词")

        crawler_type_var.set(config.CRAWLER_TYPE)
        async with async_playwright() as playwright:
            if config.ENABLE_CDP_MODE:
                self.browser_context = await self.launch_browser_with_cdp(
                    playwright,
                    None,
                    self.user_agent,
                    headless=config.CDP_HEADLESS,
                )
            else:
                self.browser_context = await self.launch_browser(
                    playwright.chromium,
                    None,
                    self.user_agent,
                    headless=config.HEADLESS,
                )
                await self.browser_context.add_init_script(path="libs/stealth.min.js")

            try:
                self.context_page = await self.browser_context.new_page()
                client = AskClient(self.context_page)
                await self.search(client, keywords)
            finally:
                await self.close()

    async def search(
        self,
        client: Optional[AskClient] = None,
        keywords: Optional[list[str]] = None,
    ) -> None:
        if client is None:
            client = AskClient(self.context_page)
        if keywords is None:
            keywords = [
                item.strip() for item in config.KEYWORDS.split(",") if item.strip()
            ]

        from store import ask as ask_store

        throttle = CommentCrawlThrottle()
        for keyword in keywords:
            source_keyword_var.set(keyword)
            utils.logger.info(f"[AskCrawler] 开始搜索关键词：{keyword}")
            count = await client.crawl_keyword(
                keyword=keyword,
                start_page=config.START_PAGE,
                max_questions=config.CRAWLER_MAX_NOTES_COUNT,
                max_answers=(
                    config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES
                    if config.ENABLE_GET_COMMENTS
                    else 0
                ),
                content_callback=ask_store.update_ask_question,
                comment_callback=(
                    lambda question_id, answers: throttle.store_comments(
                        ask_store.batch_update_ask_answers,
                        question_id,
                        answers,
                    )
                ),
                page_callback=throttle.finish_page,
                item_callback=throttle.wait_between_items,
            )
            if client.last_stop_reason:
                utils.logger.warning(
                    f"[AskCrawler] 关键词 {keyword} 触发风控，已安全保存 "
                    f"{count} 个问题，请稍后继续"
                )
                break
            utils.logger.info(
                f"[AskCrawler] 关键词 {keyword} 已保存 {count} 个问题"
            )

    async def launch_browser(
        self,
        chromium: BrowserType,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        if config.SAVE_LOGIN_STATE:
            user_data_dir = os.path.join(
                os.getcwd(), "browser_data", config.USER_DATA_DIR % config.PLATFORM
            )
            return await chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                accept_downloads=True,
                headless=headless,
                proxy=playwright_proxy,
                viewport={"width": 1920, "height": 1080},
                user_agent=user_agent,
                channel="chrome",
            )

        browser = await chromium.launch(
            headless=headless,
            proxy=playwright_proxy,
            channel="chrome",
        )
        return await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=user_agent,
        )

    async def launch_browser_with_cdp(
        self,
        playwright: Playwright,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        utils.logger.info("[AskCrawler] 使用 CDP 模式连接真实浏览器")
        manager = CDPBrowserManager()
        self.cdp_manager = manager
        try:
            browser_context = await manager.launch_and_connect(
                playwright=playwright,
                playwright_proxy=playwright_proxy,
                user_agent=user_agent,
                headless=headless,
            )
            browser_info = await manager.get_browser_info()
            utils.logger.info(f"[AskCrawler] CDP 浏览器信息：{browser_info}")
            return browser_context
        except Exception as exc:
            await manager.cleanup()
            self.cdp_manager = None
            raise RuntimeError(f"120ask CDP 浏览器连接失败：{exc}") from exc

    async def close(self) -> None:
        if self.cdp_manager:
            await self.cdp_manager.cleanup()
            self.cdp_manager = None
        else:
            await self.browser_context.close()
        utils.logger.info("[AskCrawler] 浏览器上下文已关闭")


__all__ = ["AskCrawler"]
