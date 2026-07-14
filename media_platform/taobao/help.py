# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


TAOBAO_BIZ_CODE_BY_HOST = {
    "item.taobao.com": "ali.china.taobao",
    "detail.tmall.com": "ali.china.tmall",
}


@dataclass(frozen=True)
class TaobaoProductUrl:
    item_id: str
    url: str
    biz_code: str


def parse_taobao_product_url(url: str) -> TaobaoProductUrl:
    """Parse a Taobao or Tmall desktop product URL."""
    normalized_url = url.strip()
    parsed = urlparse(normalized_url)
    item_ids = parse_qs(parsed.query).get("id", [])
    biz_code = TAOBAO_BIZ_CODE_BY_HOST.get(parsed.hostname or "")
    if (
        parsed.scheme != "https"
        or not biz_code
        or parsed.path != "/item.htm"
        or len(item_ids) != 1
        or not item_ids[0].isdigit()
    ):
        raise ValueError(
            "仅支持标准淘宝或天猫商品链接，例如："
            "https://item.taobao.com/item.htm?id=752598787556 或 "
            "https://detail.tmall.com/item.htm?id=703832297172"
        )
    return TaobaoProductUrl(
        item_id=item_ids[0],
        url=normalized_url,
        biz_code=biz_code,
    )
