# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import json
from typing import Any, Dict, List

import config
from base.base_crawler import AbstractStore
from tools import utils

from ._store_impl import JdExcelStoreImplement, JdFileStoreImplement


class JdStoreFactory:
    STORES = {
        "csv": JdFileStoreImplement,
        "json": JdFileStoreImplement,
        "jsonl": JdFileStoreImplement,
        "excel": JdExcelStoreImplement,
    }

    @staticmethod
    def create_store() -> AbstractStore:
        store_class = JdStoreFactory.STORES.get(config.SAVE_DATA_OPTION)
        if not store_class:
            raise ValueError(
                f"京东评论不支持保存为 {config.SAVE_DATA_OPTION}，"
                "请选择 csv、json、jsonl 或 excel"
            )
        return store_class()


def _normalize_comment(sku_id: str, comment: Dict[str, Any]) -> Dict[str, Any]:
    comment_data = comment.get("commentData")
    if isinstance(comment_data, dict):
        content = comment_data.get("content", "")
    else:
        content = comment_data or ""

    pictures = comment.get("pictureInfoList") or []
    picture_urls = [
        picture.get("picURL", "")
        for picture in pictures
        if isinstance(picture, dict) and picture.get("picURL")
    ]
    return {
        "comment_id": comment.get("guid", ""),
        "sku_id": sku_id,
        "content": content,
        "score": comment.get("score"),
        "create_time": comment.get("creationTime", ""),
        "nickname": comment.get("userNickName", ""),
        "avatar": comment.get("userImgURL", ""),
        "product_color": comment.get("productColor", ""),
        "product_size": comment.get("productSize", ""),
        "pictures": ",".join(picture_urls),
        "like_count": comment.get("usefulVoteCount", 0),
        "reply_count": comment.get("replyCount", 0),
        "raw_comment": json.dumps(comment, ensure_ascii=False),
        "last_modify_ts": utils.get_current_timestamp(),
    }


async def batch_update_jd_comments(
    sku_id: str, comments: List[Dict[str, Any]]
) -> None:
    if not comments:
        return
    store = JdStoreFactory.create_store()
    for comment in comments:
        normalized_comment = _normalize_comment(sku_id, comment)
        utils.logger.info(
            f"[store.jd] 保存商品 {sku_id} 评论 "
            f"{normalized_comment['comment_id']}"
        )
        await store.store_comment(normalized_comment)


__all__ = ["JdStoreFactory", "batch_update_jd_comments"]
