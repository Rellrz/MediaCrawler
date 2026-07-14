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

from ._store_impl import TaobaoExcelStoreImplement, TaobaoFileStoreImplement


class TaobaoStoreFactory:
    STORES = {
        "csv": TaobaoFileStoreImplement,
        "json": TaobaoFileStoreImplement,
        "jsonl": TaobaoFileStoreImplement,
        "excel": TaobaoExcelStoreImplement,
    }

    @staticmethod
    def create_store() -> AbstractStore:
        store_class = TaobaoStoreFactory.STORES.get(config.SAVE_DATA_OPTION)
        if not store_class:
            raise ValueError(
                f"淘宝评论不支持保存为 {config.SAVE_DATA_OPTION}，"
                "请选择 csv、json、jsonl 或 excel"
            )
        return store_class()


def _normalize_comment(item_id: str, comment: Dict[str, Any]) -> Dict[str, Any]:
    pictures = comment.get("pictures") or []
    return {
        "comment_id": comment["comment_id"],
        "item_id": item_id,
        "content": comment.get("content", ""),
        "score": comment.get("score"),
        "create_time": comment.get("create_time", ""),
        "user_id": comment.get("user_id", ""),
        "nickname": comment.get("nickname", ""),
        "avatar": comment.get("avatar", ""),
        "sku_info": comment.get("sku_info", ""),
        "pictures": ",".join(pictures),
        "like_count": comment.get("like_count", 0),
        "reply_content": comment.get("reply_content", ""),
        "append_content": comment.get("append_content", ""),
        "append_time": comment.get("append_time", ""),
        "raw_comment": json.dumps(
            comment.get("raw_comment", comment), ensure_ascii=False
        ),
        "last_modify_ts": utils.get_current_timestamp(),
    }


async def batch_update_taobao_comments(
    item_id: str, comments: List[Dict[str, Any]]
) -> None:
    if not comments:
        return
    store = TaobaoStoreFactory.create_store()
    for comment in comments:
        normalized_comment = _normalize_comment(item_id, comment)
        utils.logger.info(
            f"[store.taobao] 保存商品 {item_id} 评论 "
            f"{normalized_comment['comment_id']}"
        )
        await store.store_comment(normalized_comment)


__all__ = ["TaobaoStoreFactory", "batch_update_taobao_comments"]
