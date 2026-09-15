from __future__ import annotations

import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from projectkoios.ingestion import (
    CONTRACT_VERSION,
    EXTRACTION_CACHE_FORMAT_VERSION,
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionCacheCorruptionError,
    ExtractionCacheSafetyError,
    ExtractionResult,
    FilesystemExtractionCache,
    IngestionManifest,
    IngestionStatus,
    SourceDocument,
    SourceSpan,
    build_extraction_cache_key,
)
from projectkoios.ingestion.identity import (
    canonical_json,
    sha256_digest,
    stable_id,
)


def _result(
    payload: bytes = b"cache fixture",
    *,
    extractor_version: str = "1+backend.1",
    configuration: str = "configuration:one",
    source_id: str = "article:cache-fixture",
) -> ExtractionResult:
    source = SourceDocument.from_bytes(
        payload,
        source_id=source_id,
        media_type="application/pdf",
        locator="fixture.pdf",
    )
    span = SourceSpan(
        source_id=source.source_id,
        source_blob_id=source.blob_id,
        page_index=0,
        printed_page_label="i",
        source_object_id="page:0:block:0",
        bounding_box=(10.0, 20.0, 100.0, 40.0),
    )
    block = ExtractedBlock.create(
        kind="text",
        source_spans=(span,),
        extraction_method="fixture",
        confidence=1.0,
        text="Cached evidence",
    )
    page = ExtractedPage(
        page_index=0,
        width=612.0,
        height=792.0,
        blocks=(block,),
        printed_page_label="i",
        coordinate_system="fixture-points",
    )
    document = ExtractedDocument.create(source=source, pages=(page,))
    configuration_digest = stable_id("configuration", configuration)
    manifest = IngestionManifest.create(
        source=source,
        extractor_name="fixture",
        extractor_version=extractor_version,
        configuration_digest=configuration_digest,
        object_ids=(document.document_id, block.block_id),
        warning_ids=(),
        status=IngestionStatus.COMPLETED,
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:01Z",
    )
    return ExtractionResult(document=document, manifest=manifest)


def _entry_path(root: Path, cache_key: str) -> Path:
    key_hash = sha256_digest(cache_key.encode())
    return (
        root
        / f"v{EXTRACTION_CACHE_FORMAT_VERSION}"
        / key_hash[:2]
        / f"{key_hash}.json"
    )


def _read_envelope(root: Path, key: str) -> dict[str, Any]:
    return json.loads(_entry_path(root, key).read_text())


def _write_envelope(root: Path, key: str, value: dict[str, Any]) -> None:
    _entry_path(root, key).write_text(canonical_json(value) + "\n")


def _rehash_result(envelope: dict[str, Any]) -> None:
    envelope["result_payload_hash"] = sha256_digest(
        canonical_json(envelope["result"]).encode()
    )


def test__filesystem_cache__deterministic_round_trip(tmp_path: Path) -> None:
    result = _result()
    cache = FilesystemExtractionCache(tmp_path / "cache")

    assert cache.get(result.manifest.cache_key) is None
    cache.put(result.manifest.cache_key, result)
    first_bytes = _entry_path(
        tmp_path / "cache", result.manifest.cache_key
    ).read_bytes()
    restored = cache.get(result.manifest.cache_key)
    cache.put(result.manifest.cache_key, result)

    assert restored == result
    assert (
        _entry_path(tmp_path / "cache", result.manifest.cache_key).read_bytes()
        == first_bytes
    )
    envelope = _read_envelope(tmp_path / "cache", result.manifest.cache_key)
    assert envelope["cache_format_version"] == "1"
    assert (
        envelope["identity"]["source_blob_id"] == result.document.source.blob_id
    )


def test__cache_key__changes_for_source_backend_configuration_and_format() -> (
    None
):
    first = _result()
    changed_source = _result(b"changed cache fixture")
    changed_logical_source = _result(source_id="article:another-fixture")
    changed_backend = _result(extractor_version="1+backend.2")
    changed_configuration = _result(configuration="configuration:two")

    assert (
        len(
            {
                first.manifest.cache_key,
                changed_source.manifest.cache_key,
                changed_logical_source.manifest.cache_key,
                changed_backend.manifest.cache_key,
                changed_configuration.manifest.cache_key,
            }
        )
        == 5
    )
    assert first.manifest.cache_key != build_extraction_cache_key(
        source_id=first.document.source.source_id,
        source_blob_id=first.document.source.blob_id,
        extractor_name=first.manifest.extractor_name,
        extractor_version=first.manifest.extractor_version,
        configuration_digest=first.manifest.configuration_digest,
        contract_version=CONTRACT_VERSION,
        cache_format_version="future",
    )


@pytest.mark.parametrize(
    "payload",
    [
        b"{",
        b"{}",
        b"\xff",
        b'{"cache_key":"one","cache_key":"two"}',
    ],
)
def test__filesystem_cache__malformed_or_truncated_entry_is_corruption(
    tmp_path: Path, payload: bytes
) -> None:
    result = _result()
    cache = FilesystemExtractionCache(tmp_path / "cache")
    cache.put(result.manifest.cache_key, result)
    _entry_path(tmp_path / "cache", result.manifest.cache_key).write_bytes(
        payload
    )

    with pytest.raises(ExtractionCacheCorruptionError):
        cache.get(result.manifest.cache_key)


def test__filesystem_cache__rejects_unsupported_format(tmp_path: Path) -> None:
    result = _result()
    root = tmp_path / "cache"
    cache = FilesystemExtractionCache(root)
    cache.put(result.manifest.cache_key, result)
    envelope = _read_envelope(root, result.manifest.cache_key)
    envelope["cache_format_version"] = "999"
    _write_envelope(root, result.manifest.cache_key, envelope)

    with pytest.raises(ExtractionCacheCorruptionError, match="unsupported"):
        cache.get(result.manifest.cache_key)


def test__filesystem_cache__rejects_key_and_payload_hash_mismatches(
    tmp_path: Path,
) -> None:
    result = _result()
    root = tmp_path / "cache"
    cache = FilesystemExtractionCache(root)
    cache.put(result.manifest.cache_key, result)
    envelope = _read_envelope(root, result.manifest.cache_key)
    envelope["cache_key_hash"] = "0" * 64
    _write_envelope(root, result.manifest.cache_key, envelope)
    with pytest.raises(ExtractionCacheCorruptionError, match="key hash"):
        cache.get(result.manifest.cache_key)

    _entry_path(root, result.manifest.cache_key).unlink()
    cache.put(result.manifest.cache_key, result)
    envelope = _read_envelope(root, result.manifest.cache_key)
    envelope["cache_key"] = "extraction-cache:sha256:" + "0" * 64
    _write_envelope(root, result.manifest.cache_key, envelope)
    with pytest.raises(ExtractionCacheCorruptionError, match="logical key"):
        cache.get(result.manifest.cache_key)

    _entry_path(root, result.manifest.cache_key).unlink()
    cache.put(result.manifest.cache_key, result)
    envelope = _read_envelope(root, result.manifest.cache_key)
    envelope["result"]["document"]["source"]["locator"] = "tampered.pdf"
    _write_envelope(root, result.manifest.cache_key, envelope)
    with pytest.raises(ExtractionCacheCorruptionError, match="payload hash"):
        cache.get(result.manifest.cache_key)


def test__filesystem_cache__excessive_json_nesting_is_corruption(
    tmp_path: Path,
) -> None:
    result = _result()
    root = tmp_path / "cache"
    cache = FilesystemExtractionCache(root)
    cache.put(result.manifest.cache_key, result)
    depth = max(10_000, sys.getrecursionlimit() * 10)
    nested_json = "[" * depth + "0" + "]" * depth
    _entry_path(root, result.manifest.cache_key).write_text(nested_json)

    with pytest.raises(ExtractionCacheCorruptionError, match="malformed JSON"):
        cache.get(result.manifest.cache_key)


def test__filesystem_cache__oversized_numeric_content_is_corruption(
    tmp_path: Path,
) -> None:
    result = _result()
    root = tmp_path / "cache"
    cache = FilesystemExtractionCache(root)
    cache.put(result.manifest.cache_key, result)
    envelope = _read_envelope(root, result.manifest.cache_key)
    envelope["result"]["document"]["pages"][0]["width"] = 10**4000
    _rehash_result(envelope)
    _write_envelope(root, result.manifest.cache_key, envelope)

    with pytest.raises(
        ExtractionCacheCorruptionError, match="representable as a number"
    ):
        cache.get(result.manifest.cache_key)


def test__filesystem_cache__escaped_lone_surrogate_is_corruption(
    tmp_path: Path,
) -> None:
    result = _result()
    root = tmp_path / "cache"
    cache = FilesystemExtractionCache(root)
    cache.put(result.manifest.cache_key, result)
    envelope = _read_envelope(root, result.manifest.cache_key)
    envelope["result"]["document"]["source"]["locator"] = "\ud800"
    _entry_path(root, result.manifest.cache_key).write_text(
        json.dumps(envelope, ensure_ascii=True), encoding="utf-8"
    )

    with pytest.raises(ExtractionCacheCorruptionError, match="not valid UTF-8"):
        cache.get(result.manifest.cache_key)


def test__filesystem_cache__invalid_unicode_key_and_result_are_rejected(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cache"
    cache = FilesystemExtractionCache(root)

    with pytest.raises(ValueError, match="valid UTF-8"):
        cache.get("\ud800")
    assert not root.exists()

    result = _result()
    source = replace(result.document.source, locator="\ud800")
    document = replace(result.document, source=source)
    invalid_result = replace(result, document=document)
    with pytest.raises(ValueError, match="valid UTF-8"):
        cache.put(result.manifest.cache_key, invalid_result)
    assert not root.exists()


def test__filesystem_cache__rejects_invalid_reconstructed_contract(
    tmp_path: Path,
) -> None:
    result = _result()
    root = tmp_path / "cache"
    cache = FilesystemExtractionCache(root)
    cache.put(result.manifest.cache_key, result)
    envelope = _read_envelope(root, result.manifest.cache_key)
    envelope["result"]["document"]["pages"][0]["blocks"][0]["block_id"] = (
        "block:sha256:" + "0" * 64
    )
    _rehash_result(envelope)
    _write_envelope(root, result.manifest.cache_key, envelope)

    with pytest.raises(ExtractionCacheCorruptionError, match="block ID"):
        cache.get(result.manifest.cache_key)


def test__filesystem_cache__rejects_cross_source_span_identity(
    tmp_path: Path,
) -> None:
    result = _result()
    root = tmp_path / "cache"
    cache = FilesystemExtractionCache(root)
    cache.put(result.manifest.cache_key, result)
    envelope = _read_envelope(root, result.manifest.cache_key)
    envelope["result"]["document"]["pages"][0]["blocks"][0]["source_spans"][0][
        "source_id"
    ] = "article:wrong-source"
    _rehash_result(envelope)
    _write_envelope(root, result.manifest.cache_key, envelope)

    with pytest.raises(ExtractionCacheCorruptionError, match="document source"):
        cache.get(result.manifest.cache_key)


def test__filesystem_cache__put_rejects_excessive_contract_nesting(
    tmp_path: Path,
) -> None:
    result = _result()
    nested: object = "leaf"
    for _ in range(sys.getrecursionlimit() + 100):
        nested = [nested]
    document = replace(result.document, metadata=nested)  # type: ignore[arg-type]
    invalid_result = replace(result, document=document)
    cache = FilesystemExtractionCache(tmp_path / "cache")

    with pytest.raises(ValueError, match="cannot be represented"):
        cache.put(result.manifest.cache_key, invalid_result)
    assert not (tmp_path / "cache").exists()


def test__filesystem_cache__put_rejects_oversized_numeric_contract(
    tmp_path: Path,
) -> None:
    result = _result()
    page = replace(result.document.pages[0], width=10**4000)
    document = replace(result.document, pages=(page,))
    invalid_result = replace(result, document=document)
    cache = FilesystemExtractionCache(tmp_path / "cache")

    with pytest.raises(ValueError, match="representable as a number"):
        cache.put(result.manifest.cache_key, invalid_result)
    assert not (tmp_path / "cache").exists()


def test__filesystem_cache__put_rejects_non_json_numeric_contract(
    tmp_path: Path,
) -> None:
    result = _result()
    block = result.document.pages[0].blocks[0]
    span = replace(block.source_spans[0], bounding_box=(math.nan, 0, 1, 1))
    invalid_block = replace(block, source_spans=(span,))
    page = replace(result.document.pages[0], blocks=(invalid_block,))
    invalid_document = replace(result.document, pages=(page,))
    invalid_result = replace(result, document=invalid_document)
    cache = FilesystemExtractionCache(tmp_path / "cache")

    with pytest.raises(ValueError, match="must be finite"):
        cache.put(result.manifest.cache_key, invalid_result)
    assert not (tmp_path / "cache").exists()


def test__filesystem_cache__failed_publication_cleans_temporary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _result()
    root = tmp_path / "cache"
    cache = FilesystemExtractionCache(root)

    def interrupted(*args: object) -> None:
        raise OSError("simulated interrupted publication")

    monkeypatch.setattr(cache, "_publish_entry", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        cache.put(result.manifest.cache_key, result)

    shard = _entry_path(root, result.manifest.cache_key).parent
    assert not _entry_path(root, result.manifest.cache_key).exists()
    assert list(shard.iterdir()) == []
    assert cache.get(result.manifest.cache_key) is None


def test__filesystem_cache__arbitrary_key_cannot_escape_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cache"
    outside = tmp_path / "outside.json"
    outside.write_text("caller-owned")
    cache = FilesystemExtractionCache(root)

    assert cache.get("../../outside.json") is None
    assert outside.read_text() == "caller-owned"
    assert all(path.is_relative_to(root) for path in root.rglob("*"))


def test__filesystem_cache__does_not_clobber_unrelated_regular_entry(
    tmp_path: Path,
) -> None:
    result = _result()
    root = tmp_path / "cache"
    entry = _entry_path(root, result.manifest.cache_key)
    entry.parent.mkdir(parents=True)
    entry.write_text("caller-owned")
    cache = FilesystemExtractionCache(root)

    with pytest.raises(ExtractionCacheCorruptionError):
        cache.put(result.manifest.cache_key, result)

    assert entry.read_text() == "caller-owned"
    assert [path.name for path in entry.parent.iterdir()] == [entry.name]


def test__filesystem_cache__rejects_entry_symlink_without_following_it(
    tmp_path: Path,
) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks unavailable")
    result = _result()
    root = tmp_path / "cache"
    outside = tmp_path / "outside.json"
    outside.write_text("caller-owned")
    cache = FilesystemExtractionCache(root)
    cache.put(result.manifest.cache_key, result)
    entry = _entry_path(root, result.manifest.cache_key)
    entry.unlink()
    entry.symlink_to(outside)

    with pytest.raises(ExtractionCacheSafetyError):
        cache.get(result.manifest.cache_key)
    with pytest.raises(ExtractionCacheSafetyError):
        cache.put(result.manifest.cache_key, result)
    assert outside.read_text() == "caller-owned"


def test__filesystem_cache__rejects_file_in_managed_directory(
    tmp_path: Path,
) -> None:
    result = _result()
    root = tmp_path / "cache"
    root.mkdir()
    managed_version = root / "v1"
    managed_version.write_text("caller surprise")
    cache = FilesystemExtractionCache(root)

    with pytest.raises(ExtractionCacheSafetyError):
        cache.put(result.manifest.cache_key, result)
    assert managed_version.read_text() == "caller surprise"


def test__filesystem_cache__rejects_symlink_in_managed_directory(
    tmp_path: Path,
) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks unavailable")
    root = tmp_path / "cache"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "v1").symlink_to(outside, target_is_directory=True)
    cache = FilesystemExtractionCache(root)

    with pytest.raises(ExtractionCacheSafetyError):
        cache.get(_result().manifest.cache_key)
    assert list(outside.iterdir()) == []


def test__filesystem_cache__unsupported_platform_fails_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "cache"
    monkeypatch.setattr(os, "supports_dir_fd", os.supports_dir_fd - {os.open})
    cache = FilesystemExtractionCache(root)

    result = _result()
    with pytest.raises(ExtractionCacheSafetyError, match="POSIX"):
        cache.get(result.manifest.cache_key)
    with pytest.raises(ExtractionCacheSafetyError, match="POSIX"):
        cache.put(result.manifest.cache_key, result)
    assert not root.exists()


def test__filesystem_cache__concurrent_identical_puts_are_valid(
    tmp_path: Path,
) -> None:
    result = _result()
    cache = FilesystemExtractionCache(tmp_path / "cache")

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(cache.put, result.manifest.cache_key, result)
            for _ in range(12)
        ]
        for future in futures:
            future.result()

    assert cache.get(result.manifest.cache_key) == result
    shard = _entry_path(tmp_path / "cache", result.manifest.cache_key).parent
    assert [path.name for path in shard.iterdir()] == [
        _entry_path(tmp_path / "cache", result.manifest.cache_key).name
    ]
