from __future__ import annotations

import os
from pathlib import Path

import pytest
from projectkoios.ingestion.documents.pdf.deserialization import (
    BaseDeserializer,
)


def test__BaseDeserializer__reads_through_one_bounded_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"bounded evidence")

    def reject_path_read(_path: Path) -> bytes:
        raise AssertionError("Path.read_bytes must not be used")

    monkeypatch.setattr(Path, "read_bytes", reject_path_read)

    assert (
        BaseDeserializer._read_regular_file(
            source,
            limit=100,
            label="source",
        )
        == b"bounded evidence"
    )


def test__BaseDeserializer__enforces_byte_limit_before_read(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"a" * 101)

    with pytest.raises(ValueError, match="exceeds its byte limit"):
        BaseDeserializer._read_regular_file(
            source,
            limit=100,
            label="source",
        )


def test__BaseDeserializer__rejects_final_component_symlink(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"evidence")
    link = tmp_path / "link.bin"
    link.symlink_to(source)

    with pytest.raises(OSError):
        BaseDeserializer._read_regular_file(
            link,
            limit=100,
            label="source",
        )


def test__BaseDeserializer__rejects_intermediate_symlink(
    tmp_path: Path,
) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    (actual / "source.bin").write_bytes(b"evidence")
    linked_directory = tmp_path / "linked"
    linked_directory.symlink_to(actual, target_is_directory=True)

    with pytest.raises(ValueError, match="must not traverse"):
        BaseDeserializer._read_regular_file(
            linked_directory / "source.bin",
            limit=100,
            label="source",
        )


def test__BaseDeserializer__rejects_file_changed_during_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"a" * 70_000)
    original_read = os.read
    changed = False

    def changing_read(descriptor: int, size: int) -> bytes:
        nonlocal changed
        content = original_read(descriptor, size)
        if content and not changed:
            changed = True
            with source.open("ab") as writer:
                writer.write(b"changed")
        return content

    monkeypatch.setattr(os, "read", changing_read)

    with pytest.raises(ValueError, match="changed while it was read"):
        BaseDeserializer._read_regular_file(
            source,
            limit=100_000,
            label="source",
        )
