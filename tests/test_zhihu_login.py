# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import base64
from unittest.mock import AsyncMock, MagicMock

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from media_platform.zhihu.login import ZhiHuLogin
from tools import crawler_util
from tools import utils


@pytest.mark.asyncio
async def test_qrcode_element_is_captured_as_base64():
    screenshot = b"rendered-svg-qrcode"
    element = MagicMock()
    element.screenshot = AsyncMock(return_value=screenshot)
    page = MagicMock()
    page.wait_for_selector = AsyncMock(return_value=element)

    result = await crawler_util.find_qrcode_img_from_element(
        page,
        element_selector=".Qrcode-qrcode",
    )

    page.wait_for_selector.assert_awaited_once_with(".Qrcode-qrcode")
    assert result == base64.b64encode(screenshot).decode("utf-8")


@pytest.mark.asyncio
async def test_zhihu_qrcode_login_uses_current_signin_page(monkeypatch):
    page = MagicMock()
    page.goto = AsyncMock()
    browser_context = MagicMock()
    login = ZhiHuLogin("qrcode", browser_context, page)
    login.check_login_state = AsyncMock(return_value=True)

    find_qrcode = AsyncMock(return_value="base64-qrcode")
    monkeypatch.setattr(utils, "find_qrcode_img_from_element", find_qrcode)
    monkeypatch.setattr(utils, "show_qrcode", MagicMock())
    monkeypatch.setattr("media_platform.zhihu.login.asyncio.sleep", AsyncMock())
    event_loop = MagicMock()
    monkeypatch.setattr("media_platform.zhihu.login.asyncio.get_running_loop", lambda: event_loop)

    await login.login_by_qrcode()

    page.goto.assert_awaited_once_with(
        "https://www.zhihu.com/signin",
        wait_until="domcontentloaded",
    )
    find_qrcode.assert_awaited_once_with(
        page,
        element_selector=".Qrcode-qrcode",
    )
    event_loop.run_in_executor.assert_called_once()


@pytest.mark.asyncio
async def test_zhihu_qrcode_timeout_has_actionable_error(monkeypatch):
    page = MagicMock()
    page.goto = AsyncMock()
    login = ZhiHuLogin("qrcode", MagicMock(), page)
    monkeypatch.setattr(
        utils,
        "find_qrcode_img_from_element",
        AsyncMock(side_effect=PlaywrightTimeoutError("timeout")),
    )

    with pytest.raises(RuntimeError, match="知乎登录二维码加载超时"):
        await login.login_by_qrcode()
