# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import asyncio
import random
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlencode

from playwright.async_api import Page

from tools import utils


class AskDataFetchError(RuntimeError):
    """Raised when 120ask cannot return usable public page data."""


class AskRiskControlError(AskDataFetchError):
    """Raised when 120ask blocks or challenges the current browser session."""


ContentCallback = Callable[[Dict[str, Any]], Awaitable[None]]
CommentCallback = Callable[[str, List[Dict[str, Any]]], Awaitable[None]]
PageCallback = Callable[[], Awaitable[None]]


class AskClient:
    SEARCH_URL = "https://so.120ask.com/"
    MAX_TRANSIENT_RETRIES = 2
    QUESTION_ID_PATTERN = re.compile(r"/question/(?P<question_id>\d+)\.htm$")
    DATETIME_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
    DOCTOR_TITLE_PATTERN = re.compile(
        r"(?P<title>主任医师|副主任医师|主治医师|住院医师|医师|医士)$"
    )
    RISK_MARKERS = (
        "验证码",
        "需要验证",
        "访问过于频繁",
        "请求过于频繁",
        "安全验证",
        "异常访问",
    )

    def __init__(self, page: Page) -> None:
        self.page = page
        self.last_stop_reason: Optional[str] = None

    @classmethod
    def _is_risk_control_error(cls, error: BaseException | str) -> bool:
        message = str(error).lower()
        return any(
            marker in message
            for marker in ("http 403", "http 429", *cls.RISK_MARKERS)
        )

    @staticmethod
    def _is_transient_error(error: BaseException) -> bool:
        message = str(error).lower()
        return any(
            marker in message
            for marker in (
                "timeout",
                "timed out",
                "net::err_",
                "http 500",
                "http 502",
                "http 503",
                "http 504",
            )
        )

    async def _navigate_once(self, url: str) -> None:
        response = await self.page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60_000,
        )
        if response is None:
            return

        status = response.status
        if status in (403, 429):
            raise AskRiskControlError(f"{url} 返回 HTTP {status}")
        if status == 404:
            raise AskDataFetchError(f"{url} 返回 HTTP 404")
        if status >= 500:
            raise RuntimeError(f"{url} 返回 HTTP {status}")
        if status >= 400:
            raise AskDataFetchError(f"{url} 返回 HTTP {status}")

    async def _navigate_with_retry(self, url: str, label: str) -> None:
        for attempt in range(self.MAX_TRANSIENT_RETRIES + 1):
            try:
                await self._navigate_once(url)
                return
            except Exception as exc:
                if isinstance(exc, AskRiskControlError) or self._is_risk_control_error(
                    exc
                ):
                    raise AskRiskControlError(str(exc)) from exc
                if isinstance(exc, AskDataFetchError):
                    raise
                if (
                    not self._is_transient_error(exc)
                    or attempt == self.MAX_TRANSIENT_RETRIES
                ):
                    raise AskDataFetchError(f"{label}请求失败：{exc}") from exc

                retry_delay = random.uniform(
                    5.0 * (2**attempt),
                    10.0 * (2**attempt),
                )
                utils.logger.warning(
                    f"[AskClient] {label}请求异常，{retry_delay:.1f} 秒后进行"
                    f"第 {attempt + 1} 次重试"
                )
                await asyncio.sleep(retry_delay)

    @classmethod
    def _raise_for_challenge(cls, page_data: Dict[str, Any], label: str) -> None:
        sample_text = " ".join(
            str(page_data.get(key) or "") for key in ("title", "body_text")
        )
        if cls._is_risk_control_error(sample_text):
            raise AskRiskControlError(f"{label}出现验证或访问频率限制：{sample_text[:120]}")

    async def get_search_page(self, keyword: str, page_number: int) -> Dict[str, Any]:
        if page_number < 1:
            raise ValueError("120ask 搜索起始页必须大于等于 1")

        search_url = f"{self.SEARCH_URL}?{urlencode({'kw': keyword, 'page': page_number})}"
        await self._navigate_with_retry(
            search_url,
            f"关键词 {keyword} 第 {page_number} 页",
        )
        page_data = await self.page.evaluate(
            """
            () => {
                const container = document.querySelector("#datalist");
                const items = container
                    ? Array.from(container.querySelectorAll(":scope > li"))
                    : [];
                const questions = items.map((item) => {
                    const anchor = item.querySelector('h3 a[href*="/question/"]');
                    if (!anchor) return null;
                    return {
                        title: (anchor.textContent || "").trim(),
                        summary: (item.querySelector(".cont")?.textContent || "").trim(),
                        url: anchor.href
                    };
                }).filter(Boolean);
                const hasNext = Array.from(
                    document.querySelectorAll(".p_pagediv a")
                ).some((anchor) => (anchor.textContent || "").trim() === "下一页");
                return {
                    title: document.title,
                    body_text: (document.body?.innerText || "").slice(0, 500),
                    has_container: Boolean(container),
                    has_next: hasNext,
                    questions
                };
            }
            """
        )
        if not isinstance(page_data, dict):
            raise AskDataFetchError("120ask 搜索页返回了无法识别的数据")
        self._raise_for_challenge(page_data, "120ask 搜索页")
        if not page_data.get("has_container"):
            raise AskDataFetchError("120ask 搜索页结构变化：缺少 #datalist")

        questions: List[Dict[str, Any]] = []
        for item in page_data.get("questions") or []:
            if not isinstance(item, dict):
                continue
            match = self.QUESTION_ID_PATTERN.search(str(item.get("url") or ""))
            if not match:
                continue
            questions.append(
                {
                    "question_id": match.group("question_id"),
                    "title": str(item.get("title") or "").strip(),
                    "summary": str(item.get("summary") or "").strip(),
                    "question_url": str(item.get("url") or "").strip(),
                }
            )
        return {"questions": questions, "has_next": bool(page_data.get("has_next"))}

    async def get_question_detail(
        self, search_item: Dict[str, Any]
    ) -> Dict[str, Any]:
        question_id = str(search_item["question_id"])
        question_url = str(search_item["question_url"])
        await self._navigate_with_retry(question_url, f"问题 {question_id} 详情页")
        page_data = await self.page.evaluate(
            """
            () => {
                const titleElement = document.querySelector("#d_askH1");
                const descriptionElement = document.querySelector("#d_msCon");
                const metadata = Array.from(
                    document.querySelectorAll(".b_askab1 span")
                ).map((item) => (item.textContent || "").trim());
                const routeNames = Array.from(
                    document.querySelectorAll('.b_route span[itemprop="name"]')
                ).map((item) => (item.textContent || "").trim()).filter(Boolean);
                const answers = Array.from(
                    document.querySelectorAll(".b_answerli")
                ).map((answer, index) => {
                    const reply = answer.querySelector('.crazy_new[id^="reply"]');
                    return {
                        reply_id: reply?.id || "",
                        content: (reply?.textContent || "").trim(),
                        doctor_name: (
                            answer.querySelector(".b_answertl .b_sp1 a")?.textContent || ""
                        ).trim(),
                        doctor_info: (
                            answer.querySelector(".b_answertl .b_sp1")?.textContent || ""
                        ).replace(/\s+/g, " ").trim(),
                        doctor_specialty: (
                            answer.querySelector(".b_answertl .b_sp2")?.textContent || ""
                        ).replace(/^擅长[:：]?\s*/, "").trim(),
                        answer_time: (
                            answer.querySelector(".b_anscont_time")?.textContent || ""
                        ).replace(/\s+/g, " ").trim(),
                        answer_index: index + 1
                    };
                });
                return {
                    title: document.title,
                    body_text: (document.body?.innerText || "").slice(0, 500),
                    has_title: Boolean(titleElement),
                    question_title: (titleElement?.textContent || "").trim(),
                    description: (descriptionElement?.textContent || "").trim(),
                    metadata,
                    category: routeNames.at(-1) || "",
                    answers
                };
            }
            """
        )
        if not isinstance(page_data, dict):
            raise AskDataFetchError(f"问题 {question_id} 详情页返回了无法识别的数据")
        self._raise_for_challenge(page_data, f"问题 {question_id} 详情页")
        if not page_data.get("has_title"):
            raise AskDataFetchError(
                f"问题 {question_id} 详情页结构变化：缺少 #d_askH1"
            )

        metadata = " ".join(
            str(item) for item in page_data.get("metadata") or []
        )
        publish_match = self.DATETIME_PATTERN.search(metadata)
        reply_match = re.search(r"(\d+)人回复", metadata)
        description = str(page_data.get("description") or "").strip()
        description = re.sub(r"^健康咨询描述[:：]?\s*", "", description)
        question = {
            "question_id": question_id,
            "title": str(page_data.get("question_title") or search_item.get("title") or "").strip(),
            "description": description,
            "category": str(page_data.get("category") or "").strip(),
            "publish_time": publish_match.group(0) if publish_match else "",
            "reply_count": int(reply_match.group(1)) if reply_match else 0,
            "question_url": question_url,
        }

        answers: List[Dict[str, Any]] = []
        for raw_answer in page_data.get("answers") or []:
            if not isinstance(raw_answer, dict):
                continue
            content = str(raw_answer.get("content") or "").strip()
            if not content:
                continue
            doctor_name = str(raw_answer.get("doctor_name") or "").strip()
            doctor_info = str(raw_answer.get("doctor_info") or "").strip()
            if doctor_name and doctor_info.startswith(doctor_name):
                doctor_info = doctor_info[len(doctor_name) :].strip()
            title_match = self.DOCTOR_TITLE_PATTERN.search(doctor_info)
            doctor_title = title_match.group("title") if title_match else ""
            doctor_hospital = (
                doctor_info[: title_match.start()].strip() if title_match else doctor_info
            )
            answer_time_text = str(raw_answer.get("answer_time") or "")
            answer_time_match = self.DATETIME_PATTERN.search(answer_time_text)
            reply_id = str(raw_answer.get("reply_id") or "").removeprefix("reply")
            answer_index = int(raw_answer.get("answer_index") or len(answers) + 1)
            answers.append(
                {
                    "comment_id": reply_id or f"{question_id}-{answer_index}",
                    "content": content,
                    "doctor_name": doctor_name,
                    "doctor_hospital": doctor_hospital,
                    "doctor_title": doctor_title,
                    "doctor_specialty": str(
                        raw_answer.get("doctor_specialty") or ""
                    ).strip(),
                    "answer_time": (
                        answer_time_match.group(0) if answer_time_match else ""
                    ),
                }
            )
        return {"question": question, "answers": answers}

    async def crawl_keyword(
        self,
        keyword: str,
        start_page: int,
        max_questions: int,
        max_answers: int,
        content_callback: ContentCallback,
        comment_callback: Optional[CommentCallback] = None,
        page_callback: Optional[PageCallback] = None,
        item_callback: Optional[PageCallback] = None,
    ) -> int:
        if start_page < 1:
            raise ValueError("120ask 搜索起始页必须大于等于 1")
        if max_questions <= 0:
            return 0

        self.last_stop_reason = None
        crawled_count = 0
        page_number = start_page
        seen_question_ids: set[str] = set()
        while crawled_count < max_questions:
            try:
                search_page = await self.get_search_page(keyword, page_number)
            except AskRiskControlError as exc:
                self.last_stop_reason = str(exc)
                utils.logger.warning(
                    f"[AskClient] 关键词 {keyword} 第 {page_number} 页触发风控，"
                    f"已安全保存 {crawled_count} 个问题，停止继续请求"
                )
                break

            questions = search_page["questions"]
            if not questions:
                break

            for item_index, search_item in enumerate(questions):
                if crawled_count >= max_questions:
                    break
                question_id = search_item["question_id"]
                if question_id in seen_question_ids:
                    continue
                seen_question_ids.add(question_id)
                try:
                    detail = await self.get_question_detail(search_item)
                except AskRiskControlError as exc:
                    self.last_stop_reason = str(exc)
                    utils.logger.warning(
                        f"[AskClient] 问题 {question_id} 触发风控，已安全保存 "
                        f"{crawled_count} 个问题，停止继续请求"
                    )
                    return crawled_count
                except AskDataFetchError as exc:
                    utils.logger.warning(
                        f"[AskClient] 跳过无法读取的问题 {question_id}：{exc}"
                    )
                    continue

                question = detail["question"]
                question.update({"keyword": keyword, "search_page": page_number})
                await content_callback(question)
                crawled_count += 1

                if comment_callback and max_answers > 0:
                    answers = detail["answers"][:max_answers]
                    for answer in answers:
                        answer.update(
                            {
                                "question_id": question_id,
                                "keyword": keyword,
                                "question_title": question["title"],
                                "question_description": question["description"],
                                "question_url": question["question_url"],
                            }
                        )
                    if answers:
                        await comment_callback(question_id, answers)

                has_more_items = item_index + 1 < len(questions)
                if item_callback and crawled_count < max_questions and has_more_items:
                    await item_callback()

            if page_callback:
                await page_callback()
            if (
                crawled_count >= max_questions
                or not search_page["has_next"]
            ):
                break
            page_number += 1

        return crawled_count


__all__ = ["AskClient", "AskDataFetchError", "AskRiskControlError"]
