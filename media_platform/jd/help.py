# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import re
from dataclasses import dataclass


JD_PRODUCT_URL_PATTERN = re.compile(
    r"^https://(?:item\.jd\.com|item\.jingdonghealth\.cn)/"
    r"(?P<sku_id>\d+)\.html(?:\?[^#]*)?$"
)


@dataclass(frozen=True)
class JdProductUrl:
    sku_id: str
    url: str


def parse_jd_product_url(url: str) -> JdProductUrl:
    """Parse a standard JD product URL and return its SKU."""
    normalized_url = url.strip()
    match = JD_PRODUCT_URL_PATTERN.fullmatch(normalized_url)
    if not match:
        raise ValueError(
            "仅支持标准京东商品链接，例如：https://item.jd.com/100012043978.html "
            "或 https://item.jingdonghealth.cn/2943746.html"
        )
    return JdProductUrl(sku_id=match.group("sku_id"), url=normalized_url)
