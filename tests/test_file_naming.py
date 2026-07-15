# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import re

from tools.async_file_writer import AsyncFileWriter
from tools.file_naming import build_data_filename, normalize_data_type


def test_filename_uses_platform_mode_type_date_and_time():
    filename = build_data_filename("tb", "detail", "comments", "json")

    assert re.fullmatch(
        r"tb_detail_comment_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.json",
        filename,
    )


def test_non_comment_item_types_are_named_content():
    assert normalize_data_type("contents") == "content"
    assert normalize_data_type("creators") == "content"
    assert normalize_data_type("contacts") == "content"
    assert normalize_data_type("dynamics") == "content"


def test_writers_in_same_process_reuse_run_timestamp(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    first_writer = AsyncFileWriter("jd", "detail")
    second_writer = AsyncFileWriter("jd", "detail")

    first_path = first_writer._get_file_path("json", "comments")
    second_path = second_writer._get_file_path("json", "comments")

    assert first_path == second_path
    assert first_path.endswith(".json")


def test_content_and_comment_paths_are_distinct(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    writer = AsyncFileWriter("xhs", "search")

    content_path = writer._get_file_path("csv", "contents")
    comment_path = writer._get_file_path("csv", "comments")

    assert "xhs_search_content_" in content_path
    assert "xhs_search_comment_" in comment_path
    assert content_path != comment_path
