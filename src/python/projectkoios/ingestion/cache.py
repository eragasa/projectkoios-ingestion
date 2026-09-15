from __future__ import annotations

import json
import math
import os
import secrets
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn, cast

from projectkoios.ingestion.cache_identity import (
    EXTRACTION_CACHE_FORMAT_VERSION,
    build_extraction_cache_key,
)
from projectkoios.ingestion.identity import canonical_json, sha256_digest
from projectkoios.ingestion.models import (
    CONTRACT_VERSION,
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionResult,
    IngestionManifest,
    IngestionStatus,
    IngestionWarning,
    SourceDocument,
    SourceSpan,
    TableOfContentsEntry,
    WarningSeverity,
)
from projectkoios.ingestion.serialization import contract_dict

_ENTRY_SUFFIX = ".json"


class ExtractionCacheError(RuntimeError):
    """Base error for filesystem extraction cache failures."""


class ExtractionCacheCorruptionError(ExtractionCacheError):
    """Raised when a cache entry exists but is not a valid cache contract."""


class ExtractionCacheSafetyError(ExtractionCacheError):
    """Raised for unsafe files or links in cache-managed paths."""


class FilesystemExtractionCache:
    """Content-addressed JSON cache rooted at a caller-supplied directory.

    Entries are atomically published without replacing an existing path after
    their file contents have been synced. Concurrent writers for one key accept
    the first complete, independently validated result for that same key.
    """

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(os.path.abspath(os.fspath(root)))

    def get(self, cache_key: str) -> ExtractionResult | None:
        self._require_platform_capabilities()
        key_hash = self._key_hash(cache_key)
        directory_fd = self._open_entry_directory(key_hash, create=False)
        if directory_fd is None:
            return None
        try:
            payload = self._read_entry(directory_fd, key_hash)
        finally:
            os.close(directory_fd)
        if payload is None:
            return None
        return self._decode_entry(payload, cache_key, key_hash)

    def put(self, cache_key: str, result: ExtractionResult) -> None:
        self._require_platform_capabilities()
        key_hash = self._key_hash(cache_key)
        try:
            serialized_result = contract_dict(result)
        except (TypeError, RecursionError) as error:
            raise ValueError(
                "result cannot be represented as a cache contract"
            ) from error
        try:
            validated_result = _decode_result(serialized_result)
            _validate_result(validated_result)
        except (
            TypeError,
            ValueError,
            KeyError,
            OverflowError,
            RecursionError,
        ) as error:
            raise ValueError(
                f"result is not a valid cacheable ExtractionResult: {error}"
            ) from error
        if cache_key != validated_result.manifest.cache_key:
            raise ValueError("cache_key must match the extraction manifest")
        try:
            result_payload_hash = sha256_digest(
                canonical_json(serialized_result).encode("utf-8")
            )
        except UnicodeEncodeError as error:
            raise ValueError(
                "result contains a string that is not valid UTF-8"
            ) from error
        except (RecursionError, ValueError) as error:
            raise ValueError(
                "result cannot be represented as canonical JSON"
            ) from error
        envelope = {
            "cache_format_version": EXTRACTION_CACHE_FORMAT_VERSION,
            "cache_key": cache_key,
            "cache_key_hash": key_hash,
            "result_payload_hash": result_payload_hash,
            "identity": _entry_identity(validated_result),
            "result": serialized_result,
        }
        try:
            payload = (canonical_json(envelope) + "\n").encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError(
                "cache envelope contains a string that is not valid UTF-8"
            ) from error
        except (RecursionError, ValueError) as error:
            raise ValueError(
                "cache envelope cannot be represented as canonical JSON"
            ) from error
        directory_fd = self._open_entry_directory(key_hash, create=True)
        assert directory_fd is not None
        try:
            self._write_entry(directory_fd, key_hash, cache_key, payload)
        finally:
            os.close(directory_fd)

    @staticmethod
    def _require_platform_capabilities() -> None:
        required_dir_fd = (os.open, os.mkdir, os.stat, os.unlink, os.link)
        dir_fd_support: set[object] = getattr(os, "supports_dir_fd", set())
        follow_support: set[object] = getattr(
            os, "supports_follow_symlinks", set()
        )
        missing = [
            f"{function.__name__}(dir_fd)"
            for function in required_dir_fd
            if function not in dir_fd_support
        ]
        if os.stat not in follow_support:
            missing.append("stat(follow_symlinks=False)")
        if os.link not in follow_support:
            missing.append("link(follow_symlinks=False)")
        if not getattr(os, "O_DIRECTORY", 0):
            missing.append("O_DIRECTORY")
        if not getattr(os, "O_NOFOLLOW", 0):
            missing.append("O_NOFOLLOW")
        if not getattr(os, "O_NONBLOCK", 0):
            missing.append("O_NONBLOCK")
        if missing:
            raise ExtractionCacheSafetyError(
                "filesystem extraction cache requires POSIX safety "
                "capabilities: " + ", ".join(missing)
            )

    @staticmethod
    def _key_hash(cache_key: str) -> str:
        if not isinstance(cache_key, str) or not cache_key:
            raise ValueError("cache_key must be a non-empty string")
        try:
            encoded_key = cache_key.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError("cache_key must be valid UTF-8") from error
        return sha256_digest(encoded_key)

    def _open_entry_directory(
        self, key_hash: str, *, create: bool
    ) -> int | None:
        root_fd = self._open_root(create=create)
        if root_fd is None:
            return None
        current_fd = root_fd
        try:
            for component in (
                f"v{EXTRACTION_CACHE_FORMAT_VERSION}",
                key_hash[:2],
            ):
                next_fd = self._open_child_directory(
                    current_fd, component, create=create
                )
                if next_fd is None:
                    os.close(current_fd)
                    return None
                os.close(current_fd)
                current_fd = next_fd
            return current_fd
        except Exception:
            os.close(current_fd)
            raise

    def _open_root(self, *, create: bool) -> int | None:
        try:
            root_status = os.lstat(self.root)
        except FileNotFoundError:
            if not create:
                return None
            try:
                self.root.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                pass
            root_status = os.lstat(self.root)
        if stat.S_ISLNK(root_status.st_mode) or not stat.S_ISDIR(
            root_status.st_mode
        ):
            raise ExtractionCacheSafetyError(
                f"cache root is not a real directory: {self.root}"
            )
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        try:
            return os.open(self.root, flags)
        except OSError as error:
            raise ExtractionCacheSafetyError(
                f"could not safely open cache root {self.root}: {error}"
            ) from error

    def _open_child_directory(
        self, parent_fd: int, name: str, *, create: bool
    ) -> int | None:
        if create:
            try:
                os.mkdir(name, dir_fd=parent_fd)
            except FileExistsError:
                pass
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        try:
            return os.open(name, flags, dir_fd=parent_fd)
        except FileNotFoundError:
            if not create:
                return None
            raise
        except OSError as error:
            raise ExtractionCacheSafetyError(
                f"cache path component {name!r} is not a safe directory: "
                f"{error}"
            ) from error

    def _read_entry(self, directory_fd: int, key_hash: str) -> bytes | None:
        filename = key_hash + _ENTRY_SUFFIX
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        try:
            entry_fd = os.open(filename, flags, dir_fd=directory_fd)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise ExtractionCacheSafetyError(
                f"could not safely open cache entry {filename}: {error}"
            ) from error
        try:
            if not stat.S_ISREG(os.fstat(entry_fd).st_mode):
                raise ExtractionCacheSafetyError(
                    f"cache entry is not a regular file: {filename}"
                )
            chunks: list[bytes] = []
            while chunk := os.read(entry_fd, 1024 * 1024):
                chunks.append(chunk)
            return b"".join(chunks)
        except OSError as error:
            raise ExtractionCacheCorruptionError(
                f"could not read cache entry {filename}: {error}"
            ) from error
        finally:
            os.close(entry_fd)

    def _write_entry(
        self,
        directory_fd: int,
        key_hash: str,
        cache_key: str,
        payload: bytes,
    ) -> None:
        filename = key_hash + _ENTRY_SUFFIX
        temporary = f".tmp-{key_hash}-{secrets.token_hex(12)}"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        temporary_fd: int | None = None
        try:
            temporary_fd = os.open(temporary, flags, 0o600, dir_fd=directory_fd)
            with os.fdopen(temporary_fd, "wb", closefd=True) as stream:
                temporary_fd = None
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                self._publish_entry(directory_fd, temporary, filename)
            except FileExistsError:
                existing_payload = self._read_entry(directory_fd, key_hash)
                if existing_payload is None:
                    raise ExtractionCacheSafetyError(
                        "cache entry disappeared during no-clobber publication"
                    ) from None
                self._decode_entry(existing_payload, cache_key, key_hash)
            os.unlink(temporary, dir_fd=directory_fd)
            os.fsync(directory_fd)
        except Exception:
            if temporary_fd is not None:
                os.close(temporary_fd)
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
            raise

    @staticmethod
    def _publish_entry(
        directory_fd: int, temporary: str, filename: str
    ) -> None:
        os.link(
            temporary,
            filename,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )

    @staticmethod
    def _decode_entry(
        payload: bytes, cache_key: str, key_hash: str
    ) -> ExtractionResult:
        try:
            text = payload.decode("utf-8")
            value = json.loads(
                text,
                object_pairs_hook=_object_without_duplicates,
                parse_constant=_reject_json_constant,
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
            RecursionError,
        ) as error:
            raise ExtractionCacheCorruptionError(
                f"cache entry is malformed JSON: {error}"
            ) from error
        try:
            envelope = _mapping(
                value,
                "cache envelope",
                {
                    "cache_format_version",
                    "cache_key",
                    "cache_key_hash",
                    "result_payload_hash",
                    "identity",
                    "result",
                },
            )
            version = _string(
                envelope["cache_format_version"], "cache_format_version"
            )
        except (TypeError, ValueError, KeyError) as error:
            raise ExtractionCacheCorruptionError(
                f"cache entry envelope is invalid: {error}"
            ) from error
        if version != EXTRACTION_CACHE_FORMAT_VERSION:
            raise ExtractionCacheCorruptionError(
                f"unsupported cache format version: {version}"
            )
        if envelope["cache_key"] != cache_key:
            raise ExtractionCacheCorruptionError(
                "cache entry logical key does not match the requested key"
            )
        if envelope["cache_key_hash"] != key_hash:
            raise ExtractionCacheCorruptionError(
                "cache entry key hash does not match its storage path"
            )
        result_value = envelope["result"]
        try:
            actual_payload_hash = sha256_digest(
                canonical_json(result_value).encode("utf-8")
            )
        except UnicodeEncodeError as error:
            raise ExtractionCacheCorruptionError(
                "cache entry result contains a string that is not valid UTF-8"
            ) from error
        except (RecursionError, ValueError) as error:
            raise ExtractionCacheCorruptionError(
                "cache entry result cannot be canonicalized"
            ) from error
        if envelope["result_payload_hash"] != actual_payload_hash:
            raise ExtractionCacheCorruptionError(
                "cache entry result payload hash mismatch"
            )
        try:
            result = _decode_result(result_value)
            _validate_result(result)
        except (
            TypeError,
            ValueError,
            KeyError,
            OverflowError,
            RecursionError,
        ) as error:
            raise ExtractionCacheCorruptionError(
                f"cache entry contains an invalid ExtractionResult: {error}"
            ) from error
        if result.manifest.cache_key != cache_key:
            raise ExtractionCacheCorruptionError(
                "cached manifest key does not match the requested key"
            )
        if envelope["identity"] != _entry_identity(result):
            raise ExtractionCacheCorruptionError(
                "cache entry identity manifest does not match its result"
            )
        return result


def _entry_identity(result: ExtractionResult) -> dict[str, object]:
    source = result.document.source
    manifest = result.manifest
    return {
        "contract_version": result.document.contract_version,
        "logical_source_id": source.source_id,
        "source_blob_id": source.blob_id,
        "source_content_hash": source.content_hash,
        "source_byte_length": source.byte_length,
        "source_media_type": source.media_type,
        "source_locator": source.locator,
        "extractor_name": manifest.extractor_name,
        "extractor_version": manifest.extractor_version,
        "configuration_digest": manifest.configuration_digest,
        "manifest_id": manifest.manifest_id,
        "document_id": result.document.document_id,
    }


def _validate_result(result: ExtractionResult) -> None:
    document = result.document
    manifest = result.manifest
    if document.contract_version != CONTRACT_VERSION:
        raise ValueError(
            f"unsupported extraction contract version: "
            f"{document.contract_version}"
        )
    if manifest.contract_version != document.contract_version:
        raise ValueError("manifest and document contract versions must match")

    source = document.source
    page_by_index = {page.page_index: page for page in document.pages}
    all_warning_ids = tuple(warning.warning_id for warning in result.warnings)
    if document.warning_ids != all_warning_ids:
        raise ValueError("document warning IDs must match result warnings")

    object_ids = [document.document_id]
    referenced_warning_ids: set[str] = set()
    expected_document = ExtractedDocument.create(
        source=source,
        pages=document.pages,
        metadata=document.metadata,
        table_of_contents=document.table_of_contents,
        warning_ids=document.warning_ids,
    )
    if document.document_id != expected_document.document_id:
        raise ValueError("document ID is not valid for its logical source")

    for page in document.pages:
        referenced_warning_ids.update(page.warning_ids)
        for block in page.blocks:
            object_ids.append(block.block_id)
            referenced_warning_ids.update(block.warning_ids)
            expected_block = ExtractedBlock.create(
                kind=block.kind,
                source_spans=block.source_spans,
                extraction_method=block.extraction_method,
                confidence=block.confidence,
                text=block.text,
                asset_id=block.asset_id,
                warning_ids=block.warning_ids,
                asset_media_type=block.asset_media_type,
                asset_mask_id=block.asset_mask_id,
                asset_mask_media_type=block.asset_mask_media_type,
            )
            if block.block_id != expected_block.block_id:
                raise ValueError(
                    "block ID is not valid for its source evidence"
                )
            for span in block.source_spans:
                _validate_span_source(span, source)
                if span.printed_page_label != page.printed_page_label:
                    raise ValueError(
                        "block span page label does not match its page"
                    )

    for entry in document.table_of_contents:
        object_ids.append(entry.entry_id)
        expected_entry = TableOfContentsEntry.create(
            source=source,
            level=entry.level,
            title=entry.title,
            destination=entry.destination,
            source_object_id=entry.source_object_id,
        )
        if entry.entry_id != expected_entry.entry_id:
            raise ValueError("table-of-contents entry ID is invalid")
        if entry.destination is not None:
            _validate_span_page(entry.destination, source, page_by_index)

    for warning in result.warnings:
        expected_warning = IngestionWarning.create(
            code=warning.code,
            severity=warning.severity,
            message=warning.message,
            object_ids=warning.object_ids,
            source_spans=warning.source_spans,
            evidence=warning.evidence,
            suggested_recovery=warning.suggested_recovery,
        )
        if warning.warning_id != expected_warning.warning_id:
            raise ValueError("warning ID is invalid")
        if not set(warning.object_ids).issubset(set(object_ids)):
            raise ValueError("warning refers to an unknown extracted object")
        for span in warning.source_spans:
            _validate_span_page(span, source, page_by_index)

    if not referenced_warning_ids.issubset(set(all_warning_ids)):
        raise ValueError("page or block refers to an unknown warning")
    if manifest.object_ids != tuple(object_ids):
        raise ValueError("manifest object IDs do not match extracted objects")
    expected_manifest = IngestionManifest.create(
        source=source,
        extractor_name=manifest.extractor_name,
        extractor_version=manifest.extractor_version,
        configuration_digest=manifest.configuration_digest,
        object_ids=manifest.object_ids,
        warning_ids=manifest.warning_ids,
        status=manifest.status,
        started_at=manifest.started_at,
        completed_at=manifest.completed_at,
    )
    if manifest.cache_key != expected_manifest.cache_key:
        raise ValueError("manifest cache key is invalid")
    if manifest.manifest_id != expected_manifest.manifest_id:
        raise ValueError("manifest ID is invalid")


def _validate_span_source(span: SourceSpan, source: SourceDocument) -> None:
    if (
        span.source_id != source.source_id
        or span.source_blob_id != source.blob_id
    ):
        raise ValueError(
            "source span does not refer to the exact result source"
        )


def _validate_span_page(
    span: SourceSpan,
    source: SourceDocument,
    page_by_index: dict[int, ExtractedPage],
) -> None:
    _validate_span_source(span, source)
    page = page_by_index.get(span.page_index)
    if page is None:
        raise ValueError("source span refers to a page absent from the result")
    if span.printed_page_label != page.printed_page_label:
        raise ValueError("source span page label does not match its page")


def _decode_result(value: object) -> ExtractionResult:
    raw = _mapping(value, "result", {"document", "manifest", "warnings"})
    return ExtractionResult(
        document=_decode_document(raw["document"]),
        manifest=_decode_manifest(raw["manifest"]),
        warnings=_tuple_of(raw["warnings"], "warnings", _decode_warning),
    )


def _decode_source(value: object) -> SourceDocument:
    raw = _mapping(
        value,
        "source",
        {
            "source_id",
            "blob_id",
            "media_type",
            "content_hash",
            "hash_algorithm",
            "byte_length",
            "locator",
        },
    )
    return SourceDocument(
        source_id=_string(raw["source_id"], "source.source_id"),
        blob_id=_string(raw["blob_id"], "source.blob_id"),
        media_type=_string(raw["media_type"], "source.media_type"),
        content_hash=_string(raw["content_hash"], "source.content_hash"),
        hash_algorithm=_string(raw["hash_algorithm"], "source.hash_algorithm"),
        byte_length=_integer(raw["byte_length"], "source.byte_length"),
        locator=_string(raw["locator"], "source.locator"),
    )


def _decode_span(value: object) -> SourceSpan:
    raw = _mapping(
        value,
        "source span",
        {
            "source_id",
            "source_blob_id",
            "page_index",
            "printed_page_label",
            "source_object_id",
            "bounding_box",
            "start_offset",
            "end_offset",
        },
    )
    box_value = raw["bounding_box"]
    bounding_box = None
    if box_value is not None:
        items = _sequence(box_value, "source span bounding_box")
        if len(items) != 4:
            raise ValueError("source span bounding_box must have four values")
        bounding_box = tuple(
            _number(item, "source span bounding_box") for item in items
        )
    return SourceSpan(
        source_id=_string(raw["source_id"], "span.source_id"),
        source_blob_id=_string(raw["source_blob_id"], "span.source_blob_id"),
        page_index=_integer(raw["page_index"], "span.page_index"),
        printed_page_label=_optional_string(
            raw["printed_page_label"], "span.printed_page_label"
        ),
        source_object_id=_optional_string(
            raw["source_object_id"], "span.source_object_id"
        ),
        bounding_box=bounding_box,  # type: ignore[arg-type]
        start_offset=_optional_integer(
            raw["start_offset"], "span.start_offset"
        ),
        end_offset=_optional_integer(raw["end_offset"], "span.end_offset"),
    )


def _decode_block(value: object) -> ExtractedBlock:
    raw = _mapping(
        value,
        "block",
        {
            "block_id",
            "kind",
            "source_spans",
            "extraction_method",
            "confidence",
            "text",
            "asset_id",
            "warning_ids",
            "asset_media_type",
            "asset_mask_id",
            "asset_mask_media_type",
        },
    )
    return ExtractedBlock(
        block_id=_string(raw["block_id"], "block.block_id"),
        kind=_string(raw["kind"], "block.kind"),
        source_spans=_tuple_of(
            raw["source_spans"], "block.source_spans", _decode_span
        ),
        extraction_method=_string(
            raw["extraction_method"], "block.extraction_method"
        ),
        confidence=_number(raw["confidence"], "block.confidence"),
        text=_optional_string(raw["text"], "block.text"),
        asset_id=_optional_string(raw["asset_id"], "block.asset_id"),
        warning_ids=_string_tuple(raw["warning_ids"], "block.warning_ids"),
        asset_media_type=_optional_string(
            raw["asset_media_type"], "block.asset_media_type"
        ),
        asset_mask_id=_optional_string(
            raw["asset_mask_id"], "block.asset_mask_id"
        ),
        asset_mask_media_type=_optional_string(
            raw["asset_mask_media_type"], "block.asset_mask_media_type"
        ),
    )


def _decode_page(value: object) -> ExtractedPage:
    raw = _mapping(
        value,
        "page",
        {
            "page_index",
            "width",
            "height",
            "blocks",
            "printed_page_label",
            "extraction_quality",
            "warning_ids",
            "coordinate_system",
        },
    )
    return ExtractedPage(
        page_index=_integer(raw["page_index"], "page.page_index"),
        width=_number(raw["width"], "page.width"),
        height=_number(raw["height"], "page.height"),
        blocks=_tuple_of(raw["blocks"], "page.blocks", _decode_block),
        printed_page_label=_optional_string(
            raw["printed_page_label"], "page.printed_page_label"
        ),
        extraction_quality=_number(
            raw["extraction_quality"], "page.extraction_quality"
        ),
        warning_ids=_string_tuple(raw["warning_ids"], "page.warning_ids"),
        coordinate_system=_string(
            raw["coordinate_system"], "page.coordinate_system"
        ),
    )


def _decode_toc_entry(value: object) -> TableOfContentsEntry:
    raw = _mapping(
        value,
        "table-of-contents entry",
        {
            "entry_id",
            "source_id",
            "source_blob_id",
            "level",
            "title",
            "destination",
            "source_object_id",
        },
    )
    return TableOfContentsEntry(
        entry_id=_string(raw["entry_id"], "toc.entry_id"),
        source_id=_string(raw["source_id"], "toc.source_id"),
        source_blob_id=_string(raw["source_blob_id"], "toc.source_blob_id"),
        level=_integer(raw["level"], "toc.level"),
        title=_string(raw["title"], "toc.title"),
        destination=(
            None
            if raw["destination"] is None
            else _decode_span(raw["destination"])
        ),
        source_object_id=_optional_string(
            raw["source_object_id"], "toc.source_object_id"
        ),
    )


def _decode_document(value: object) -> ExtractedDocument:
    raw = _mapping(
        value,
        "document",
        {
            "document_id",
            "source",
            "pages",
            "metadata",
            "warning_ids",
            "contract_version",
            "table_of_contents",
        },
    )
    return ExtractedDocument(
        document_id=_string(raw["document_id"], "document.document_id"),
        source=_decode_source(raw["source"]),
        pages=_tuple_of(raw["pages"], "document.pages", _decode_page),
        metadata=_metadata(raw["metadata"], "document.metadata"),
        warning_ids=_string_tuple(raw["warning_ids"], "document.warning_ids"),
        contract_version=_string(
            raw["contract_version"], "document.contract_version"
        ),
        table_of_contents=_tuple_of(
            raw["table_of_contents"],
            "document.table_of_contents",
            _decode_toc_entry,
        ),
    )


def _decode_warning(value: object) -> IngestionWarning:
    raw = _mapping(
        value,
        "warning",
        {
            "warning_id",
            "code",
            "severity",
            "message",
            "object_ids",
            "source_spans",
            "evidence",
            "suggested_recovery",
        },
    )
    return IngestionWarning(
        warning_id=_string(raw["warning_id"], "warning.warning_id"),
        code=_string(raw["code"], "warning.code"),
        severity=WarningSeverity(_string(raw["severity"], "warning.severity")),
        message=_string(raw["message"], "warning.message"),
        object_ids=_string_tuple(raw["object_ids"], "warning.object_ids"),
        source_spans=_tuple_of(
            raw["source_spans"], "warning.source_spans", _decode_span
        ),
        evidence=_metadata(raw["evidence"], "warning.evidence"),
        suggested_recovery=_optional_string(
            raw["suggested_recovery"], "warning.suggested_recovery"
        ),
    )


def _decode_manifest(value: object) -> IngestionManifest:
    raw = _mapping(
        value,
        "manifest",
        {
            "manifest_id",
            "source_id",
            "source_blob_id",
            "source_content_hash",
            "extractor_name",
            "extractor_version",
            "configuration_digest",
            "object_ids",
            "warning_ids",
            "cache_key",
            "status",
            "started_at",
            "completed_at",
            "contract_version",
        },
    )
    return IngestionManifest(
        manifest_id=_string(raw["manifest_id"], "manifest.manifest_id"),
        source_id=_string(raw["source_id"], "manifest.source_id"),
        source_blob_id=_string(
            raw["source_blob_id"], "manifest.source_blob_id"
        ),
        source_content_hash=_string(
            raw["source_content_hash"], "manifest.source_content_hash"
        ),
        extractor_name=_string(
            raw["extractor_name"], "manifest.extractor_name"
        ),
        extractor_version=_string(
            raw["extractor_version"], "manifest.extractor_version"
        ),
        configuration_digest=_string(
            raw["configuration_digest"], "manifest.configuration_digest"
        ),
        object_ids=_string_tuple(raw["object_ids"], "manifest.object_ids"),
        warning_ids=_string_tuple(raw["warning_ids"], "manifest.warning_ids"),
        cache_key=_string(raw["cache_key"], "manifest.cache_key"),
        status=IngestionStatus(_string(raw["status"], "manifest.status")),
        started_at=_string(raw["started_at"], "manifest.started_at"),
        completed_at=_optional_string(
            raw["completed_at"], "manifest.completed_at"
        ),
        contract_version=_string(
            raw["contract_version"], "manifest.contract_version"
        ),
    )


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    raise ValueError(f"invalid JSON number: {value}")


def _mapping(
    value: object, name: str, expected_keys: set[str]
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be an object")
    keys = set(value)
    if keys != expected_keys:
        missing = sorted(expected_keys - keys)
        extra = sorted(keys - expected_keys)
        raise ValueError(
            f"{name} fields do not match schema; missing={missing}, "
            f"extra={extra}"
        )
    return value


def _sequence(value: object, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be an array")
    return value


def _tuple_of[T](
    value: object, name: str, decoder: Callable[[object], T]
) -> tuple[T, ...]:
    return tuple(decoder(item) for item in _sequence(value, name))


def _string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error
    return value


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _string(value, name)


def _integer(value: object, name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    return value


def _optional_integer(value: object, name: str) -> int | None:
    if value is None:
        return None
    return _integer(value, name)


def _number(value: object, name: str) -> int | float:
    if type(value) not in (int, float):
        raise TypeError(f"{name} must be a number")
    number = cast("int | float", value)
    try:
        finite = math.isfinite(number)
    except OverflowError as error:
        raise ValueError(f"{name} must be representable as a number") from error
    if not finite:
        raise ValueError(f"{name} must be finite")
    return number


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    return tuple(_string(item, name) for item in _sequence(value, name))


def _metadata(value: object, name: str) -> tuple[tuple[str, str], ...]:
    items: list[tuple[str, str]] = []
    for raw_pair in _sequence(value, name):
        pair = _sequence(raw_pair, name)
        if len(pair) != 2:
            raise ValueError(f"{name} entries must have two values")
        items.append((_string(pair[0], name), _string(pair[1], name)))
    return tuple(items)


__all__ = [
    "EXTRACTION_CACHE_FORMAT_VERSION",
    "ExtractionCacheCorruptionError",
    "ExtractionCacheError",
    "ExtractionCacheSafetyError",
    "FilesystemExtractionCache",
    "build_extraction_cache_key",
]
