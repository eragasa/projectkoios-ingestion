"""Disk extraction-artifact binding and reader tests."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest
from projectkoios.ingestion.integrations.disk.extraction.artifact import (
    reader as reader_module,
)
from projectkoios.ingestion.integrations.disk.extraction.artifact.binding import (  # noqa: E501
    DiskExtractionArtifactBinding,
    DiskExtractionArtifactBindingInventory,
)
from projectkoios.ingestion.integrations.disk.extraction.artifact.reader import (  # noqa: E501
    DiskExtractionArtifactReader,
)
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.artifact.validation.reader.error import (  # noqa: E501
    ExtractionArtifactReaderError,
)

_AUTHORITY = "authority:test-private-extraction-artifact-read"
_REFERENCE = "artifact:test:extraction-001"


def _binding(
    path: str = "artifacts/extraction.json",
) -> DiskExtractionArtifactBinding:
    return DiskExtractionArtifactBinding(
        artifact_reference=_REFERENCE,
        relative_path=path,
    )


def _reader(
    root: Path,
    *,
    binding: DiskExtractionArtifactBinding | None = None,
) -> DiskExtractionArtifactReader:
    selected = binding if binding is not None else _binding()
    return DiskExtractionArtifactReader(
        root=root,
        bindings=DiskExtractionArtifactBindingInventory(selected),
        authority_id=_AUTHORITY,
    )


def test__binding_inventory__requires_canonical_one_to_one_bindings() -> None:
    first = DiskExtractionArtifactBinding(
        artifact_reference="artifact:test:a",
        relative_path="a.json",
    )
    second = DiskExtractionArtifactBinding(
        artifact_reference="artifact:test:b",
        relative_path="b.json",
    )

    inventory = DiskExtractionArtifactBindingInventory(first, second)

    assert inventory.require("artifact:test:b") == second
    assert inventory.binding_inventory_id
    with pytest.raises(ValueError, match="sorted"):
        DiskExtractionArtifactBindingInventory(second, first)
    with pytest.raises(ValueError, match="unique"):
        DiskExtractionArtifactBindingInventory(first, first)
    with pytest.raises(ValueError, match="root-relative"):
        DiskExtractionArtifactBinding(
            artifact_reference="artifact:test:c",
            relative_path="../c.json",
        )


def test__reader__reads_exact_bound_regular_file(tmp_path: Path) -> None:
    target = tmp_path / "artifacts" / "extraction.json"
    target.parent.mkdir()
    target.write_bytes(b'{"contract":"current"}')
    reader = _reader(tmp_path)

    content = reader.read(
        artifact_reference=_REFERENCE,
        authority_id=_AUTHORITY,
        maximum_bytes=1_000,
    )

    assert content == b'{"contract":"current"}'
    assert reader.implementation_id == "disk-extraction-artifact-reader:1.0"


def test__reader__requires_exact_authority_and_binding(tmp_path: Path) -> None:
    reader = _reader(tmp_path)

    with pytest.raises(ExtractionArtifactReaderError) as authority:
        reader.read(
            artifact_reference=_REFERENCE,
            authority_id="authority:wrong",
            maximum_bytes=1_000,
        )
    with pytest.raises(ExtractionArtifactReaderError) as binding:
        reader.read(
            artifact_reference="artifact:test:missing",
            authority_id=_AUTHORITY,
            maximum_bytes=1_000,
        )

    assert (
        authority.value.disposition
        is ExtractionActionDisposition.AUTHORITY_REQUIRED
    )
    assert binding.value.code == "artifact_binding_missing"


def test__reader__rejects_missing_and_oversized_files(tmp_path: Path) -> None:
    reader = _reader(tmp_path)
    target = tmp_path / "artifacts" / "extraction.json"

    with pytest.raises(ExtractionArtifactReaderError) as missing:
        reader.read(
            artifact_reference=_REFERENCE,
            authority_id=_AUTHORITY,
            maximum_bytes=4,
        )

    target.parent.mkdir()
    target.write_bytes(b"12345")
    with pytest.raises(ExtractionArtifactReaderError) as oversized:
        reader.read(
            artifact_reference=_REFERENCE,
            authority_id=_AUTHORITY,
            maximum_bytes=4,
        )

    assert missing.value.code == "artifact_unavailable"
    assert oversized.value.code == "artifact_byte_limit_exceeded"


def test__reader__rejects_final_and_intermediate_symlinks(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"outside")
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "extraction.json").symlink_to(outside)

    with pytest.raises(ExtractionArtifactReaderError) as final:
        _reader(tmp_path).read(
            artifact_reference=_REFERENCE,
            authority_id=_AUTHORITY,
            maximum_bytes=1_000,
        )

    (artifacts / "extraction.json").unlink()
    real = tmp_path / "real"
    real.mkdir()
    (real / "extraction.json").write_bytes(b"content")
    artifacts.rmdir()
    artifacts.symlink_to(real, target_is_directory=True)
    with pytest.raises(ExtractionArtifactReaderError) as intermediate:
        _reader(tmp_path).read(
            artifact_reference=_REFERENCE,
            authority_id=_AUTHORITY,
            maximum_bytes=1_000,
        )

    assert final.value.code == "unsafe_artifact_path"
    assert intermediate.value.code == "unsafe_artifact_path"


def test__reader__rejects_nonregular_fifo_without_blocking(
    tmp_path: Path,
) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    target = artifacts / "extraction.json"
    os.mkfifo(target)

    with pytest.raises(ExtractionArtifactReaderError) as raised:
        _reader(tmp_path).read(
            artifact_reference=_REFERENCE,
            authority_id=_AUTHORITY,
            maximum_bytes=1_000,
        )

    assert raised.value.code == "unsafe_artifact_path"


def test__reader__rejects_replaced_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    target = root / "artifacts" / "extraction.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"authorized")
    reader = _reader(root)

    root.rename(tmp_path / "authorized-root")
    replacement = tmp_path / "root" / "artifacts"
    replacement.mkdir(parents=True)
    (replacement / "extraction.json").write_bytes(b"replacement")

    with pytest.raises(ExtractionArtifactReaderError) as raised:
        reader.read(
            artifact_reference=_REFERENCE,
            authority_id=_AUTHORITY,
            maximum_bytes=1_000,
        )

    assert raised.value.code == "unsafe_artifact_root"


def test__reader__rejects_ctime_change_during_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "artifacts" / "extraction.json"
    target.parent.mkdir()
    target.write_bytes(b"same-size")
    reader = _reader(tmp_path)
    actual_fstat = os.fstat
    regular_observations = 0

    def changed_fstat(descriptor: int) -> os.stat_result | SimpleNamespace:
        nonlocal regular_observations
        observed = actual_fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode):
            return observed
        regular_observations += 1
        if regular_observations == 1:
            return observed
        return SimpleNamespace(
            st_mode=observed.st_mode,
            st_size=observed.st_size,
            st_mtime_ns=observed.st_mtime_ns,
            st_ctime_ns=observed.st_ctime_ns + 1,
        )

    monkeypatch.setattr(reader_module.os, "fstat", changed_fstat)

    with pytest.raises(ExtractionArtifactReaderError) as raised:
        reader.read(
            artifact_reference=_REFERENCE,
            authority_id=_AUTHORITY,
            maximum_bytes=1_000,
        )

    assert raised.value.code == "artifact_changed_during_read"


def test__reader__rejects_symlink_root(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)

    with pytest.raises(ValueError, match="root cannot be a symlink"):
        _reader(linked)
