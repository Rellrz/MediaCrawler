# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import asyncio
from datetime import datetime, timedelta

from api.schemas.crawler import CrawlerStartRequest
from api.services.crawler_manager import CrawlerManager


def build_request() -> CrawlerStartRequest:
    return CrawlerStartRequest(
        platform="xhs",
        crawler_type="search",
        keywords="测试",
        max_notes_count=10,
    )


def prepare_manager() -> CrawlerManager:
    manager = CrawlerManager()
    manager.task_id = "task-1"
    manager.current_config = build_request()
    manager.started_at = datetime.now() - timedelta(seconds=12)
    return manager


def test_completed_task_status_contains_result_summary():
    manager = prepare_manager()

    manager._set_terminal_result("completed", exit_code=0)
    result = manager.get_status()

    assert result["task_id"] == "task-1"
    assert result["outcome"] == "completed"
    assert result["platform"] == "xhs"
    assert result["crawler_type"] == "search"
    assert result["exit_code"] == 0
    assert result["finished_at"] is not None
    assert result["duration_seconds"] >= 12
    assert result["error_message"] is None


def test_failed_task_status_preserves_error_summary():
    manager = prepare_manager()

    manager._set_terminal_result(
        "failed",
        exit_code=1,
        error_message="Page.wait_for_selector timeout",
    )
    result = manager.get_status()

    assert result["outcome"] == "failed"
    assert result["exit_code"] == 1
    assert result["error_message"] == "Page.wait_for_selector timeout"


def test_stopped_task_status_keeps_task_configuration():
    manager = prepare_manager()

    manager._set_terminal_result("stopped", exit_code=-15)
    result = manager.get_status()

    assert result["outcome"] == "stopped"
    assert result["platform"] == "xhs"
    assert result["crawler_type"] == "search"
    assert result["exit_code"] == -15


def test_latest_error_message_uses_last_error_log():
    manager = prepare_manager()
    manager._create_log_entry("first error", "error")
    manager._create_log_entry("some information", "info")
    manager._create_log_entry("final error", "error")

    assert manager._latest_error_message() == "final error"


class FinishedProcess:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode
        self.stdout = self

    def poll(self):
        return self.returncode

    def read(self):
        return ""


class StoppableProcess:
    def __init__(self) -> None:
        self.returncode = None

    def poll(self):
        return self.returncode

    def send_signal(self, signal_number):
        self.returncode = -signal_number

    def kill(self):
        self.returncode = -9


def test_read_output_marks_zero_exit_as_completed():
    manager = prepare_manager()
    manager.status = "running"
    manager.process = FinishedProcess(0)

    asyncio.run(manager._read_output())
    result = manager.get_status()

    assert result["status"] == "idle"
    assert result["outcome"] == "completed"
    assert result["exit_code"] == 0


def test_read_output_marks_nonzero_exit_as_failed():
    manager = prepare_manager()
    manager.status = "running"
    manager.process = FinishedProcess(2)
    manager._create_log_entry("request failed", "error")

    asyncio.run(manager._read_output())
    result = manager.get_status()

    assert result["status"] == "idle"
    assert result["outcome"] == "failed"
    assert result["exit_code"] == 2
    assert result["error_message"] == "request failed"


def test_stop_marks_active_task_as_stopped():
    manager = prepare_manager()
    manager.status = "running"
    manager.process = StoppableProcess()

    assert asyncio.run(manager.stop()) is True
    result = manager.get_status()

    assert result["status"] == "idle"
    assert result["outcome"] == "stopped"
    assert result["exit_code"] is not None
