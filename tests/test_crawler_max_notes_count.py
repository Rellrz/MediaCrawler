# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import asyncio

import pytest
from pydantic import ValidationError

import config
from api.schemas.crawler import CrawlerStartRequest
from api.services.crawler_manager import CrawlerManager
from cmd_arg.arg import parse_cmd


def build_request(max_notes_count: int) -> CrawlerStartRequest:
    return CrawlerStartRequest(
        platform="xhs",
        crawler_type="search",
        keywords="test",
        max_notes_count=max_notes_count,
    )


def test_request_rejects_non_positive_max_notes_count():
    with pytest.raises(ValidationError):
        build_request(0)


def test_crawler_command_contains_max_notes_count():
    command = CrawlerManager()._build_command(build_request(37))

    option_index = command.index("--max_notes_count")
    assert command[option_index + 1] == "37"


def test_cli_sets_max_notes_count(monkeypatch):
    monkeypatch.setattr(config, "CRAWLER_MAX_NOTES_COUNT", 15)

    result = asyncio.run(parse_cmd(["--max_notes_count", "37"]))

    assert result.max_notes_count == 37
    assert config.CRAWLER_MAX_NOTES_COUNT == 37
