# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

from typing import Any, Dict, List

import config
from base.base_crawler import AbstractStore
from tools import utils

from ._store_impl import AskExcelStoreImplement, AskFileStoreImplement


class AskStoreFactory:
    STORES = {
        "csv": AskFileStoreImplement,
        "json": AskFileStoreImplement,
        "jsonl": AskFileStoreImplement,
        "excel": AskExcelStoreImplement,
    }

    @staticmethod
    def create_store() -> AbstractStore:
        store_class = AskStoreFactory.STORES.get(config.SAVE_DATA_OPTION)
        if not store_class:
            raise ValueError(
                f"120ask 数据不支持保存为 {config.SAVE_DATA_OPTION}，"
                "请选择 csv、json、jsonl 或 excel"
            )
        return store_class()


def _normalize_question(question: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "question_id": str(question.get("question_id") or ""),
        "keyword": str(question.get("keyword") or ""),
        "title": str(question.get("title") or ""),
        "description": str(question.get("description") or ""),
        "category": str(question.get("category") or ""),
        "publish_time": str(question.get("publish_time") or ""),
        "reply_count": int(question.get("reply_count") or 0),
        "question_url": str(question.get("question_url") or ""),
        "search_page": int(question.get("search_page") or 0),
        "last_modify_ts": utils.get_current_timestamp(),
    }


def _normalize_answer(
    question_id: str,
    answer: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "comment_id": str(answer.get("comment_id") or ""),
        "question_id": question_id,
        "keyword": str(answer.get("keyword") or ""),
        "question_title": str(answer.get("question_title") or ""),
        "question_description": str(answer.get("question_description") or ""),
        "content": str(answer.get("content") or ""),
        "doctor_name": str(answer.get("doctor_name") or ""),
        "doctor_hospital": str(answer.get("doctor_hospital") or ""),
        "doctor_title": str(answer.get("doctor_title") or ""),
        "doctor_specialty": str(answer.get("doctor_specialty") or ""),
        "answer_time": str(answer.get("answer_time") or ""),
        "question_url": str(answer.get("question_url") or ""),
        "last_modify_ts": utils.get_current_timestamp(),
    }


async def update_ask_question(question: Dict[str, Any]) -> None:
    normalized_question = _normalize_question(question)
    utils.logger.info(
        f"[store.ask] 保存问题 {normalized_question['question_id']}"
    )
    store = AskStoreFactory.create_store()
    await store.store_content(normalized_question)
    if config.SAVE_DATA_OPTION == "excel":
        store.flush()


async def batch_update_ask_answers(
    question_id: str,
    answers: List[Dict[str, Any]],
) -> None:
    if not answers:
        return
    store = AskStoreFactory.create_store()
    for answer in answers:
        normalized_answer = _normalize_answer(question_id, answer)
        utils.logger.info(
            f"[store.ask] 保存问题 {question_id} 的医生回复 "
            f"{normalized_answer['comment_id']}"
        )
        await store.store_comment(normalized_answer)


__all__ = [
    "AskStoreFactory",
    "batch_update_ask_answers",
    "update_ask_question",
]
