from __future__ import annotations

import errno
import os
import stat
from pathlib import Path
from types import SimpleNamespace

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

    with pytest.raises(
        ValueError,
        match="symbolic link or reparse point",
    ):
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

    with pytest.raises(
        ValueError,
        match="symbolic link or reparse point",
    ):
        BaseDeserializer._read_regular_file(
            linked_directory / "source.bin",
            limit=100,
            label="source",
        )


def test__BaseDeserializer__reads_safe_parent_components(
    tmp_path: Path,
) -> None:
    traversed = tmp_path / "traversed"
    traversed.mkdir()
    source = tmp_path / "source.bin"
    source.write_bytes(b"evidence")

    assert (
        BaseDeserializer._read_regular_file(
            traversed / ".." / "source.bin",
            limit=100,
            label="source",
        )
        == b"evidence"
    )


def test__BaseDeserializer__does_not_normalize_away_missing_component(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"evidence")

    with pytest.raises(FileNotFoundError):
        BaseDeserializer._read_regular_file(
            tmp_path / "missing" / ".." / "source.bin",
            limit=100,
            label="source",
        )


def test__BaseDeserializer__rejects_symlink_before_parent_component(
    tmp_path: Path,
) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    source = tmp_path / "source.bin"
    source.write_bytes(b"evidence")
    linked_directory = tmp_path / "linked"
    linked_directory.symlink_to(actual, target_is_directory=True)

    with pytest.raises(
        ValueError,
        match="symbolic link or reparse point",
    ):
        BaseDeserializer._read_regular_file(
            linked_directory / ".." / "source.bin",
            limit=100,
            label="source",
        )


def test__BaseDeserializer__pins_opened_intermediate_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trusted = tmp_path / "trusted"
    trusted.mkdir()
    (trusted / "source.bin").write_bytes(b"trusted")
    attacker = tmp_path / "attacker"
    attacker.mkdir()
    (attacker / "source.bin").write_bytes(b"attacker")
    retained = tmp_path / "retained"
    original_open = os.open
    substituted = False

    monkeypatch.delattr(os, "O_NOFOLLOW_ANY", raising=False)

    def substituting_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal substituted
        if path == "source.bin" and dir_fd is not None and not substituted:
            substituted = True
            trusted.rename(retained)
            trusted.symlink_to(attacker, target_is_directory=True)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(
        os,
        "supports_dir_fd",
        {*os.supports_dir_fd, substituting_open},
    )
    monkeypatch.setattr(os, "open", substituting_open)

    assert (
        BaseDeserializer._read_regular_file(
            trusted / "source.bin",
            limit=100,
            label="source",
        )
        == b"trusted"
    )
    assert substituted


def test__BaseDeserializer__fails_closed_without_safe_open_capability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"evidence")
    monkeypatch.delattr(os, "O_NOFOLLOW_ANY", raising=False)
    monkeypatch.delattr(os, "O_NOFOLLOW", raising=False)

    with pytest.raises(OSError) as captured:
        BaseDeserializer._read_regular_file(
            source,
            limit=100,
            label="source",
        )

    assert captured.value.errno == errno.ENOTSUP
    assert "reparse points" in str(captured.value)


def test__BaseDeserializer__classifies_reparse_point_open_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = SimpleNamespace(
        st_mode=stat.S_IFREG,
        st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
    )
    monkeypatch.setattr(os, "stat", lambda *args, **kwargs: opened)

    with pytest.raises(ValueError, match="reparse point"):
        BaseDeserializer._raise_path_open_error(
            "source.bin",
            "source",
            OSError(errno.EACCES, "platform-specific open failure"),
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
