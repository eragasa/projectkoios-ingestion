"""Authoritative disk journal for extraction publications."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import ClassVar

from projectkoios.ingestion.serialization import serialize_contract
from projectkoios.ingestion.storage.extraction.base import (
    AbstractExtractionPublicationStore,
)
from projectkoios.ingestion.storage.extraction.error import (
    ExtractionPublicationError,
)
from projectkoios.ingestion.storage.extraction.publication.record import (
    ExtractionPublicationRecord,
)
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)
from projectkoios.ingestion.storage.extraction.publication.result import (
    ExtractionPublicationResult,
)


class DiskExtractionPublicationStore(AbstractExtractionPublicationStore):
    """Create-once payload objects plus a checksummed append-only journal."""

    MAX_PAYLOAD_BYTES: ClassVar[int] = 512_000_000
    MAX_JOURNAL_BYTES: ClassVar[int] = 256_000_000
    MAX_RECORD_BYTES: ClassVar[int] = 32_768

    def __init__(self, root: Path) -> None:
        if not isinstance(root, Path):
            raise TypeError("disk extraction store root must be a Path")
        self.root = root.expanduser().resolve()
        self.objects = self.root / "objects"
        self.journal = self.root / "publications.jsonl"
        self._prepare_directory(self.root)
        self._prepare_directory(self.objects)
        self._prepare_journal()

    def publish(
        self,
        *,
        request: ExtractionPublicationRequest,
    ) -> ExtractionPublicationResult:
        if type(request) is not ExtractionPublicationRequest:
            raise TypeError("request must be an ExtractionPublicationRequest")
        payload = serialize_contract(request.extraction).encode("utf-8")
        if not payload or len(payload) > self.MAX_PAYLOAD_BYTES:
            raise ExtractionPublicationError(
                "extraction publication payload size is out of bounds"
            )
        payload_sha256 = hashlib.sha256(payload).hexdigest()
        with self._exclusive_journal():
            records = self.records()
            for record in records:
                if record.request_id != request.request_id:
                    continue
                if (
                    record.payload_sha256 != payload_sha256
                    or record.document_id
                    != request.extraction.document.document_id
                ):
                    raise ExtractionPublicationError(
                        "publication request identity has conflicting content"
                    )
                self._verify_payload(record)
                return self._result(record, replayed=True)
            if any(
                record.manifest_id
                == request.extraction.manifest.manifest_id
                and record.payload_sha256 != payload_sha256
                for record in records
            ):
                raise ExtractionPublicationError(
                    "extraction manifest was already published differently"
                )
            self._write_payload(payload_sha256, payload)
            previous = records[-1].record_sha256 if records else None
            record = ExtractionPublicationRecord.create(
                sequence=len(records) + 1,
                request_id=request.request_id,
                document_id=request.extraction.document.document_id,
                manifest_id=request.extraction.manifest.manifest_id,
                payload_sha256=payload_sha256,
                payload_byte_size=len(payload),
                previous_record_sha256=previous,
            )
            self._append_record(record)
            return self._result(record, replayed=False)

    def records(self) -> tuple[ExtractionPublicationRecord, ...]:
        """Validate and return the complete journal prefix."""

        self._require_safe_file(self.journal)
        size = self.journal.stat().st_size
        if size > self.MAX_JOURNAL_BYTES:
            raise ExtractionPublicationError("publication journal is too large")
        content = self.journal.read_bytes()
        lines = content.splitlines(keepends=True)
        if lines and not lines[-1].endswith(b"\n"):
            lines.pop()
        records: list[ExtractionPublicationRecord] = []
        previous: str | None = None
        for sequence, line in enumerate(lines, start=1):
            if len(line) > self.MAX_RECORD_BYTES:
                raise ExtractionPublicationError(
                    "publication journal record is too large"
                )
            try:
                value = json.loads(line)
                record = ExtractionPublicationRecord(**value)
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                raise ExtractionPublicationError(
                    "publication journal contains an invalid record"
                ) from error
            if (
                record.sequence != sequence
                or record.previous_record_sha256 != previous
            ):
                raise ExtractionPublicationError(
                    "publication journal chain is inconsistent"
                )
            self._verify_payload(record)
            records.append(record)
            previous = record.record_sha256
        return tuple(records)

    def payload(self, record: ExtractionPublicationRecord) -> bytes:
        """Return one exact verified recovery payload."""

        if type(record) is not ExtractionPublicationRecord:
            raise TypeError("record must be an ExtractionPublicationRecord")
        return self._verify_payload(record)

    def _prepare_directory(self, path: Path) -> None:
        if path.is_symlink():
            raise ExtractionPublicationError(
                "disk extraction store directory cannot be a symlink"
            )
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            raise ExtractionPublicationError(
                "disk extraction store directory permissions are too broad"
            )

    def _prepare_journal(self) -> None:
        if self.journal.is_symlink():
            raise ExtractionPublicationError(
                "publication journal cannot be a symlink"
            )
        descriptor = os.open(
            self.journal,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
            0o600,
        )
        os.close(descriptor)
        self._require_safe_file(self.journal)

    def _require_safe_file(self, path: Path) -> None:
        if path.is_symlink() or not path.is_file():
            raise ExtractionPublicationError(
                "disk extraction store file is missing or unsafe"
            )
        if stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise ExtractionPublicationError(
                "disk extraction store file permissions are too broad"
            )

    def _payload_path(self, digest: str) -> Path:
        directory = self.objects / digest[:2]
        self._prepare_directory(directory)
        return directory / f"{digest}.json"

    def _write_payload(self, digest: str, content: bytes) -> None:
        target = self._payload_path(digest)
        if target.exists():
            self._require_safe_file(target)
            if target.read_bytes() != content:
                raise ExtractionPublicationError(
                    "content-addressed publication payload conflicts"
                )
            return
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".publication-",
            dir=target.parent,
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, target, follow_symlinks=False)
            except FileExistsError:
                self._require_safe_file(target)
                if target.read_bytes() != content:
                    raise ExtractionPublicationError(
                        "content-addressed publication payload conflicts"
                    ) from None
            directory_descriptor = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        finally:
            temporary.unlink(missing_ok=True)

    @contextmanager
    def _exclusive_journal(self) -> Iterator[None]:
        descriptor = os.open(
            self.journal,
            os.O_RDWR | os.O_NOFOLLOW,
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            content = os.pread(descriptor, self.MAX_JOURNAL_BYTES + 1, 0)
            if len(content) > self.MAX_JOURNAL_BYTES:
                raise ExtractionPublicationError(
                    "publication journal is too large"
                )
            if content and not content.endswith(b"\n"):
                complete_size = content.rfind(b"\n") + 1
                os.ftruncate(descriptor, complete_size)
                os.fsync(descriptor)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _append_record(self, record: ExtractionPublicationRecord) -> None:
        line = (serialize_contract(record) + "\n").encode("utf-8")
        if len(line) > self.MAX_RECORD_BYTES:
            raise ExtractionPublicationError(
                "publication journal record is too large"
            )
        descriptor = os.open(
            self.journal,
            os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW,
        )
        try:
            remaining = memoryview(line)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise ExtractionPublicationError(
                        "publication journal write did not progress"
                    )
                remaining = remaining[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _verify_payload(self, record: ExtractionPublicationRecord) -> bytes:
        path = self._payload_path(record.payload_sha256)
        self._require_safe_file(path)
        content = path.read_bytes()
        if (
            len(content) != record.payload_byte_size
            or hashlib.sha256(content).hexdigest()
            != record.payload_sha256
        ):
            raise ExtractionPublicationError(
                "publication recovery payload is corrupt"
            )
        return content

    @staticmethod
    def _result(
        record: ExtractionPublicationRecord,
        *,
        replayed: bool,
    ) -> ExtractionPublicationResult:
        return ExtractionPublicationResult(
            request_id=record.request_id,
            document_id=record.document_id,
            payload_sha256=record.payload_sha256,
            payload_byte_size=record.payload_byte_size,
            journal_sequence=record.sequence,
            replayed=replayed,
        )
