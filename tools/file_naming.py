# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

from datetime import datetime


RUN_TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def normalize_data_type(item_type: str) -> str:
    """Map stored item categories to the public content/comment file types."""
    return "comment" if item_type.lower() in {"comment", "comments"} else "content"


def build_data_file_stem(
    platform: str,
    crawler_type: str,
    item_type: str,
) -> str:
    """Build one process-stable output filename stem."""
    data_type = normalize_data_type(item_type)
    return f"{platform}_{crawler_type}_{data_type}_{RUN_TIMESTAMP}"


def build_data_filename(
    platform: str,
    crawler_type: str,
    item_type: str,
    extension: str,
) -> str:
    """Build a complete output filename with a normalized extension."""
    normalized_extension = extension.removeprefix(".")
    return (
        f"{build_data_file_stem(platform, crawler_type, item_type)}"
        f".{normalized_extension}"
    )
