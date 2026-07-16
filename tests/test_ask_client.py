# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import asyncio

from media_platform.ask.client import (
    AskClient,
    AskRiskControlError,
)


class FakeResponse:
    def __init__(self, status: int = 200) -> None:
        self.status = status


class FakePage:
    def __init__(self, payloads, statuses=None) -> None:
        self.payloads = list(payloads)
        self.statuses = list(statuses or [200] * len(self.payloads))
        self.urls = []

    async def goto(self, url, **kwargs):
        self.urls.append((url, kwargs))
        return FakeResponse(self.statuses.pop(0))

    async def evaluate(self, script):
        return self.payloads.pop(0)


def search_payload(question_id: str = "104632506", has_next: bool = True):
    return {
        "title": "搜索_有问必答网_快速问医生",
        "body_text": "搜索结果",
        "has_container": True,
        "has_next": has_next,
        "questions": [
            {
                "title": "小儿七星茶怎么喝",
                "summary": "搜索摘要",
                "url": f"https://www.120ask.com/question/{question_id}.htm",
            }
        ],
    }


def detail_payload():
    return {
        "title": "小儿七星茶怎么喝_有问必答",
        "body_text": "问题详情",
        "has_title": True,
        "question_title": "小儿七星茶怎么喝",
        "description": "健康咨询描述：小儿七星茶怎么喝",
        "metadata": ["保密 | 0个月", "2022-06-14 02:23:31", "1人回复"],
        "category": "小儿内科",
        "answers": [
            {
                "reply_id": "reply1417651",
                "content": "病情分析：按说明书使用。",
                "doctor_name": "刘锋",
                "doctor_info": "刘锋 九江市妇幼保健院 主治医师",
                "doctor_specialty": "小儿外科",
                "answer_time": "2022-06-14 06:43:15 我要投诉",
                "answer_index": 1,
            }
        ],
    }


def test_search_page_uses_configured_page_and_extracts_question_id():
    page = FakePage([search_payload()])

    result = asyncio.run(AskClient(page).get_search_page("小儿七星茶", 3))

    assert "page=3" in page.urls[0][0]
    assert "%E5%B0%8F%E5%84%BF" in page.urls[0][0]
    assert result["questions"][0]["question_id"] == "104632506"
    assert result["has_next"] is True


def test_question_detail_extracts_question_and_doctor_answer():
    page = FakePage([detail_payload()])
    client = AskClient(page)

    result = asyncio.run(
        client.get_question_detail(
            {
                "question_id": "104632506",
                "question_url": "https://www.120ask.com/question/104632506.htm",
                "title": "搜索标题",
            }
        )
    )

    assert result["question"] == {
        "question_id": "104632506",
        "title": "小儿七星茶怎么喝",
        "description": "小儿七星茶怎么喝",
        "category": "小儿内科",
        "publish_time": "2022-06-14 02:23:31",
        "reply_count": 1,
        "question_url": "https://www.120ask.com/question/104632506.htm",
    }
    assert result["answers"][0]["comment_id"] == "1417651"
    assert result["answers"][0]["doctor_hospital"] == "九江市妇幼保健院"
    assert result["answers"][0]["doctor_title"] == "主治医师"
    assert result["answers"][0]["answer_time"] == "2022-06-14 06:43:15"


def test_crawl_keyword_honors_start_page_question_and_answer_limits(monkeypatch):
    client = AskClient(None)
    search_pages = []
    stored_questions = []
    stored_answer_batches = []
    completed_pages = []
    item_waits = []

    async def get_search_page(keyword, page_number):
        search_pages.append(page_number)
        return {
            "questions": [
                {
                    "question_id": str(page_number * 100 + index),
                    "title": f"问题 {index}",
                    "question_url": (
                        f"https://www.120ask.com/question/"
                        f"{page_number * 100 + index}.htm"
                    ),
                }
                for index in range(3)
            ],
            "has_next": True,
        }

    async def get_question_detail(search_item):
        return {
            "question": {
                "question_id": search_item["question_id"],
                "title": search_item["title"],
                "description": "描述",
                "category": "内科",
                "publish_time": "",
                "reply_count": 3,
                "question_url": search_item["question_url"],
            },
            "answers": [
                {"comment_id": f"{search_item['question_id']}-{index}"}
                for index in range(3)
            ],
        }

    async def store_question(question):
        stored_questions.append(question)

    async def store_answers(question_id, answers):
        stored_answer_batches.append((question_id, answers))

    async def finish_page():
        completed_pages.append(True)

    async def wait_item():
        item_waits.append(True)

    monkeypatch.setattr(client, "get_search_page", get_search_page)
    monkeypatch.setattr(client, "get_question_detail", get_question_detail)

    count = asyncio.run(
        client.crawl_keyword(
            keyword="测试",
            start_page=4,
            max_questions=5,
            max_answers=2,
            content_callback=store_question,
            comment_callback=store_answers,
            page_callback=finish_page,
            item_callback=wait_item,
        )
    )

    assert count == 5
    assert search_pages == [4, 5]
    assert len(stored_questions) == 5
    assert all(len(batch[1]) == 2 for batch in stored_answer_batches)
    assert all(
        answer["question_title"].startswith("问题 ")
        and answer["question_description"] == "描述"
        for _, answers in stored_answer_batches
        for answer in answers
    )
    assert len(completed_pages) == 2
    assert len(item_waits) == 3


def test_risk_control_stops_without_losing_stored_questions(monkeypatch):
    client = AskClient(None)
    stored_questions = []

    async def get_search_page(keyword, page_number):
        if page_number == 2:
            raise AskRiskControlError("HTTP 403")
        return {
            "questions": [
                {
                    "question_id": "1",
                    "title": "问题",
                    "question_url": "https://www.120ask.com/question/1.htm",
                }
            ],
            "has_next": True,
        }

    async def get_question_detail(search_item):
        return {
            "question": {
                **search_item,
                "description": "描述",
                "category": "",
                "publish_time": "",
                "reply_count": 0,
            },
            "answers": [],
        }

    async def store_question(question):
        stored_questions.append(question)

    monkeypatch.setattr(client, "get_search_page", get_search_page)
    monkeypatch.setattr(client, "get_question_detail", get_question_detail)

    count = asyncio.run(
        client.crawl_keyword(
            "测试",
            start_page=1,
            max_questions=2,
            max_answers=0,
            content_callback=store_question,
        )
    )

    assert count == 1
    assert len(stored_questions) == 1
    assert client.last_stop_reason == "HTTP 403"
