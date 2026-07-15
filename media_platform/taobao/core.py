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
    Error as PlaywrightError,
    Page,
    Playwright,
    async_playwright,
)

import config
from base.base_crawler import AbstractCrawler
from tools import utils
from tools.cdp_browser import CDPBrowserManager
from tools.comment_crawl_throttle import create_comment_page_callback
from var import crawler_type_var

from .client import TaobaoClient, TaobaoDataFetchError
from .help import parse_taobao_product_url


class TaobaoCrawler(AbstractCrawler):
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
        if config.CRAWLER_TYPE != "detail":
            raise ValueError("淘宝平台当前仅支持 detail 模式")
        if not config.TB_SPECIFIED_PRODUCT_URL_LIST:
            raise ValueError("请至少提供一个淘宝商品链接")
        if not config.ENABLE_GET_COMMENTS:
            utils.logger.info("[TaobaoCrawler] 评论抓取已关闭，无需执行淘宝爬虫")
            return

        crawler_type_var.set(config.CRAWLER_TYPE)
        async with async_playwright() as playwright:
            if config.ENABLE_CDP_MODE:
                self.browser_context = await self.launch_browser_with_cdp(
                    playwright, None, self.user_agent, headless=config.CDP_HEADLESS
                )
            else:
                self.browser_context = await self.launch_browser(
                    playwright.chromium, None, self.user_agent, headless=config.HEADLESS
                )
                await self.browser_context.add_init_script(path="libs/stealth.min.js")

            try:
                self.context_page = await self.browser_context.new_page()
                client = TaobaoClient(self.context_page)
                from store import taobao as taobao_store

                for product_url in config.TB_SPECIFIED_PRODUCT_URL_LIST:
                    product = parse_taobao_product_url(product_url)
                    utils.logger.info(
                        f"[TaobaoCrawler] 开始获取商品 {product.item_id} 的评论"
                    )
                    await self._open_product_page(product.url)
                    comments = await client.get_comments(
                        product.item_id,
                        product.biz_code,
                        config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES,
                        config.START_PAGE,
                        callback=create_comment_page_callback(
                            taobao_store.batch_update_taobao_comments
                        ),
                    )
                    if client.last_stop_reason:
                        utils.logger.warning(
                            f"[TaobaoCrawler] 商品 {product.item_id} 触发淘宝风控，"
                            f"已安全保存 {len(comments)} 条评论，请稍后继续"
                        )
                    else:
                        utils.logger.info(
                            f"[TaobaoCrawler] 商品 {product.item_id} 已保存 "
                            f"{len(comments)} 条评论"
                        )
            except TaobaoDataFetchError:
                raise
            finally:
                await self.close()

    async def _open_product_page(self, product_url: str) -> None:
        try:
            await self.context_page.goto(
                product_url,
                wait_until="domcontentloaded",
                timeout=60_000,
            )
            await self.context_page.wait_for_function(
                "typeof window.lib?.mtop?.request === 'function'",
                timeout=120_000,
            )
        except PlaywrightError as exc:
            raise TaobaoDataFetchError(
                "淘宝商品页未能加载 MTOP 环境，请在打开的浏览器中完成登录，"
                "并检查网络连接或页面验证码"
            ) from exc

    async def search(self) -> None:
        raise NotImplementedError("淘宝平台当前不支持 search 模式")

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
            headless=headless, proxy=playwright_proxy, channel="chrome"
        )
        return await browser.new_context(
            viewport={"width": 1920, "height": 1080}, user_agent=user_agent
        )

    async def launch_browser_with_cdp(
        self,
        playwright: Playwright,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        """Connect to Chrome through the repository CDP browser manager."""
        utils.logger.info("[TaobaoCrawler] 使用 CDP 模式连接真实浏览器")
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
            utils.logger.info(f"[TaobaoCrawler] CDP 浏览器信息：{browser_info}")
            return browser_context
        except Exception as exc:
            await manager.cleanup()
            self.cdp_manager = None
            raise RuntimeError(f"淘宝 CDP 浏览器连接失败：{exc}") from exc

    async def close(self) -> None:
        """Close the active browser using the matching lifecycle."""
        if self.cdp_manager:
            await self.cdp_manager.cleanup()
            self.cdp_manager = None
        else:
            await self.browser_context.close()
        utils.logger.info("[TaobaoCrawler] 浏览器上下文已关闭")
