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


def test_rename_data_file_preserves_extension_and_content(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    file_path = data_dir / "jd" / "old.json"
    file_path.parent.mkdir(parents=True)
    file_path.write_text('[{"id": 1}]', encoding="utf-8")
    monkeypatch.setattr(data_router, "DATA_DIR", data_dir)

    result = asyncio.run(
        data_router.rename_data_file(
            "jd/old.json", data_router.RenameDataFileRequest(new_name="京东 评论")
        )
    )

    renamed_path = data_dir / "jd" / "京东 评论.json"
    assert result == {
        "success": True,
        "old_path": "jd/old.json",
        "path": "jd/京东 评论.json",
        "name": "京东 评论.json",
    }
    assert not file_path.exists()
    assert renamed_path.read_text(encoding="utf-8") == '[{"id": 1}]'


@pytest.mark.parametrize("new_name", ["", "   ", "../outside", "nested/name", "nested\\name"])
def test_rename_rejects_invalid_file_name(tmp_path, monkeypatch, new_name):
    file_path = tmp_path / "source.csv"
    file_path.write_text("id\n1\n", encoding="utf-8")
    monkeypatch.setattr(data_router, "DATA_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            data_router.rename_data_file(
                "source.csv", data_router.RenameDataFileRequest(new_name=new_name)
            )
        )

    assert exc_info.value.status_code == 400
    assert file_path.exists()


def test_rename_rejects_existing_target(tmp_path, monkeypatch):
    source = tmp_path / "source.xlsx"
    target = tmp_path / "target.xlsx"
    source.write_bytes(b"source")
    target.write_bytes(b"target")
    monkeypatch.setattr(data_router, "DATA_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            data_router.rename_data_file(
                "source.xlsx", data_router.RenameDataFileRequest(new_name="target")
            )
        )

    assert exc_info.value.status_code == 409
    assert source.read_bytes() == b"source"
    assert target.read_bytes() == b"target"


def test_rename_rejects_missing_source(tmp_path, monkeypatch):
    monkeypatch.setattr(data_router, "DATA_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            data_router.rename_data_file(
                "missing.json", data_router.RenameDataFileRequest(new_name="renamed")
            )
        )

    assert exc_info.value.status_code == 404


def test_rename_rejects_unchanged_name(tmp_path, monkeypatch):
    file_path = tmp_path / "source.json"
    file_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(data_router, "DATA_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            data_router.rename_data_file(
                "source.json", data_router.RenameDataFileRequest(new_name="source")
            )
        )

    assert exc_info.value.status_code == 400
    assert file_path.exists()


def test_rename_rejects_path_outside_data_directory(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    outside_file = tmp_path / "outside.json"
    outside_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(data_router, "DATA_DIR", data_dir)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            data_router.rename_data_file(
                "../outside.json", data_router.RenameDataFileRequest(new_name="renamed")
            )
        )

    assert exc_info.value.status_code == 403
    assert outside_file.exists()
