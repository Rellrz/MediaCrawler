# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import asyncio

import pytest
from click import BadParameter
from pydantic import ValidationError

import config
from api.schemas.crawler import CrawlerStartRequest
from api.services.crawler_manager import CrawlerManager
from cmd_arg.arg import parse_cmd


def build_request(**overrides) -> CrawlerStartRequest:
    values = {
        "platform": "xhs",
        "max_notes_count": 10,
        "comment_interval_min": 0.5,
        "comment_interval_max": 1.5,
        "page_interval_min": 2,
        "page_interval_max": 4,
        "periodic_pause_page_count": 5,
        "periodic_pause_min": 20,
        "periodic_pause_max": 40,
    }
    values.update(overrides)
    return CrawlerStartRequest(**values)


@pytest.mark.parametrize(
    ("minimum_field", "maximum_field"),
    [
        ("comment_interval_min", "comment_interval_max"),
        ("page_interval_min", "page_interval_max"),
        ("periodic_pause_min", "periodic_pause_max"),
    ],
)
def test_request_rejects_reversed_speed_range(minimum_field, maximum_field):
    with pytest.raises(ValidationError):
        build_request(**{minimum_field: 2, maximum_field: 1})


def test_request_rejects_invalid_speed_values():
    with pytest.raises(ValidationError):
        build_request(comment_interval_min=-1)
    with pytest.raises(ValidationError):
        build_request(periodic_pause_page_count=0)


def test_crawler_command_contains_crawl_speed_options():
    command = CrawlerManager()._build_command(build_request())

    expected = {
        "--comment_interval_min": "0.5",
        "--comment_interval_max": "1.5",
        "--page_interval_min": "2.0",
        "--page_interval_max": "4.0",
        "--periodic_pause_page_count": "5",
        "--periodic_pause_min": "20.0",
        "--periodic_pause_max": "40.0",
    }
    for option, value in expected.items():
        assert command[command.index(option) + 1] == value


def test_cli_sets_crawl_speed_config(monkeypatch):
    monkeypatch.setattr(config, "COMMENT_INTERVAL_MIN", 0)
    monkeypatch.setattr(config, "COMMENT_INTERVAL_MAX", 0)
    monkeypatch.setattr(config, "PAGE_INTERVAL_MIN", 2)
    monkeypatch.setattr(config, "PAGE_INTERVAL_MAX", 5)
    monkeypatch.setattr(config, "PERIODIC_PAUSE_PAGE_COUNT", 5)
    monkeypatch.setattr(config, "PERIODIC_PAUSE_MIN", 20)
    monkeypatch.setattr(config, "PERIODIC_PAUSE_MAX", 40)

    result = asyncio.run(
        parse_cmd(
            [
                "--comment_interval_min", "1",
                "--comment_interval_max", "2",
                "--page_interval_min", "3",
                "--page_interval_max", "6",
                "--periodic_pause_page_count", "7",
                "--periodic_pause_min", "30",
                "--periodic_pause_max", "60",
            ]
        )
    )

    assert result.comment_interval_min == 1
    assert result.comment_interval_max == 2
    assert result.page_interval_min == 3
    assert result.page_interval_max == 6
    assert result.periodic_pause_page_count == 7
    assert result.periodic_pause_min == 30
    assert result.periodic_pause_max == 60


def test_cli_rejects_reversed_crawl_speed_range():
    with pytest.raises(BadParameter, match="minimum cannot exceed"):
        asyncio.run(
            parse_cmd(
                [
                    "--page_interval_min",
                    "6",
                    "--page_interval_max",
                    "3",
                ]
            )
        )
