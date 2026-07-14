# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

import asyncio

import pytest
from fastapi import HTTPException

from api.routers import data as data_router


def test_delete_supported_data_file(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    file_path = data_dir / "jd" / "comments.json"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(data_router, "DATA_DIR", data_dir)

    result = asyncio.run(data_router.delete_data_file("jd/comments.json"))

    assert result == {"success": True, "path": "jd/comments.json"}
    assert not file_path.exists()


def test_delete_missing_data_file(tmp_path, monkeypatch):
    monkeypatch.setattr(data_router, "DATA_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(data_router.delete_data_file("missing.json"))

    assert exc_info.value.status_code == 404


def test_delete_rejects_directory(tmp_path, monkeypatch):
    directory = tmp_path / "jd"
    directory.mkdir()
    monkeypatch.setattr(data_router, "DATA_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(data_router.delete_data_file("jd"))

    assert exc_info.value.status_code == 400


def test_delete_rejects_path_outside_data_directory(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    outside_file = tmp_path / "outside.json"
    outside_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(data_router, "DATA_DIR", data_dir)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(data_router.delete_data_file("../outside.json"))

    assert exc_info.value.status_code == 403
    assert outside_file.exists()


def test_delete_rejects_unsupported_file_type(tmp_path, monkeypatch):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("do not delete", encoding="utf-8")
    monkeypatch.setattr(data_router, "DATA_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(data_router.delete_data_file("notes.txt"))

    assert exc_info.value.status_code == 400
    assert file_path.exists()
