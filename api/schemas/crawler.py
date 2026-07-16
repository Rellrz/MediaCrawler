# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/schemas/crawler.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator


class PlatformEnum(str, Enum):
    """Supported media platforms"""
    XHS = "xhs"
    DOUYIN = "dy"
    KUAISHOU = "ks"
    BILIBILI = "bili"
    WEIBO = "wb"
    TIEBA = "tieba"
    ZHIHU = "zhihu"
    JD = "jd"
    TAOBAO = "tb"


class LoginTypeEnum(str, Enum):
    """Login method"""
    QRCODE = "qrcode"
    PHONE = "phone"
    COOKIE = "cookie"


class CrawlerTypeEnum(str, Enum):
    """Crawler type"""
    SEARCH = "search"
    DETAIL = "detail"
    CREATOR = "creator"


class SaveDataOptionEnum(str, Enum):
    """Data save option"""
    CSV = "csv"
    DB = "db"
    JSON = "json"
    JSONL = "jsonl"
    SQLITE = "sqlite"
    MONGODB = "mongodb"
    EXCEL = "excel"


class CrawlerStartRequest(BaseModel):
    """Crawler start request"""
    platform: PlatformEnum
    login_type: LoginTypeEnum = LoginTypeEnum.QRCODE
    crawler_type: CrawlerTypeEnum = CrawlerTypeEnum.SEARCH
    keywords: str = ""  # Keywords for search mode
    specified_ids: str = ""  # Post/video ID list for detail mode, comma-separated
    creator_ids: str = ""  # Creator ID list for creator mode, comma-separated
    start_page: int = 1
    max_notes_count: int = Field(ge=1)
    max_comments_count: int = Field(default=10, ge=1)
    enable_comments: bool = True
    enable_sub_comments: bool = False
    save_option: SaveDataOptionEnum = SaveDataOptionEnum.JSONL
    cookies: str = ""
    headless: bool = False
    comment_interval_min: float = Field(default=0, ge=0)
    comment_interval_max: float = Field(default=0, ge=0)
    page_interval_min: float = Field(default=2, ge=0)
    page_interval_max: float = Field(default=5, ge=0)
    periodic_pause_page_count: int = Field(default=5, ge=1)
    periodic_pause_min: float = Field(default=20, ge=0)
    periodic_pause_max: float = Field(default=40, ge=0)

    @model_validator(mode="after")
    def validate_crawl_speed_ranges(self):
        ranges = (
            ("comment_interval", self.comment_interval_min, self.comment_interval_max),
            ("page_interval", self.page_interval_min, self.page_interval_max),
            ("periodic_pause", self.periodic_pause_min, self.periodic_pause_max),
        )
        for name, minimum, maximum in ranges:
            if minimum > maximum:
                raise ValueError(f"{name}_min cannot exceed {name}_max")
        return self


class CrawlerStatusResponse(BaseModel):
    """Crawler status response"""
    status: Literal["idle", "running", "stopping", "error"]
    platform: Optional[str] = None
    crawler_type: Optional[str] = None
    started_at: Optional[str] = None
    error_message: Optional[str] = None


class LogEntry(BaseModel):
    """Log entry"""
    id: int
    timestamp: str
    level: Literal["info", "warning", "error", "success", "debug"]
    message: str


class DataFileInfo(BaseModel):
    """Data file information"""
    name: str
    path: str
    size: int
    modified_at: str
    record_count: Optional[int] = None
