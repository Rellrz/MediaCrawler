# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

from pathlib import Path


WEBUI_DIR = Path("api/webui")


def test_task_result_dialog_is_loaded_by_webui():
    index = (WEBUI_DIR / "index.html").read_text(encoding="utf-8")

    assert '<script defer src="/static/task-result-dialog.js"></script>' in index


def test_task_result_dialog_handles_all_terminal_outcomes():
    script = (WEBUI_DIR / "task-result-dialog.js").read_text(encoding="utf-8")

    for outcome in ("completed", "failed", "stopped"):
        assert f"{outcome}:" in script
    assert "/api/ws/status" in script
    assert "/api/data/files" in script
    assert "sessionStorage" in script
    assert "viewData" in script
    assert "viewLogs" in script


def test_task_completion_notification_is_configurable():
    script = (WEBUI_DIR / "task-result-dialog.js").read_text(encoding="utf-8")

    assert "mediacrawler_task_completion_notification" in script
    assert '!== "false"' in script
    assert "任务结束通知" in script
    assert "Notification.requestPermission()" in script
    assert "new Notification" in script
    assert "document.hidden" in script
    assert "document.hasFocus()" in script
    assert "data-task-completion-notification-setting" in script
