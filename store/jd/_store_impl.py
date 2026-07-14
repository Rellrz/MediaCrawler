# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

from typing import Dict

import config
from base.base_crawler import AbstractStore
from tools.async_file_writer import AsyncFileWriter
from var import crawler_type_var


class JdFileStoreImplement(AbstractStore):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.writer = AsyncFileWriter(
            platform="jd", crawler_type=crawler_type_var.get()
        )

    async def store_content(self, content_item: Dict) -> None:
        raise NotImplementedError("京东平台当前仅保存商品评论")

    async def store_comment(self, comment_item: Dict) -> None:
        if config.SAVE_DATA_OPTION == "csv":
            await self.writer.write_to_csv(item_type="comments", item=comment_item)
        elif config.SAVE_DATA_OPTION == "json":
            await self.writer.write_single_item_to_json(
                item_type="comments", item=comment_item
            )
        elif config.SAVE_DATA_OPTION == "jsonl":
            await self.writer.write_to_jsonl(item_type="comments", item=comment_item)
        else:
            raise ValueError(
                f"京东评论不支持保存为 {config.SAVE_DATA_OPTION}，"
                "请选择 csv、json、jsonl 或 excel"
            )

    async def store_creator(self, creator: Dict) -> None:
        raise NotImplementedError("京东平台当前不保存创作者信息")


class JdExcelStoreImplement:
    def __new__(cls, *args, **kwargs):
        from store.excel_store_base import ExcelStoreBase

        return ExcelStoreBase.get_instance(
            platform="jd", crawler_type=crawler_type_var.get()
        )
