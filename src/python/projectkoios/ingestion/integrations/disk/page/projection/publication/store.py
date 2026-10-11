"""Atomic content-addressed disk journal for page-projection publication."""

from __future__ import annotations

import fcntl
import os
import uuid
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.json.parser import JsonParser
from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.page.projection.identity import (
    fingerprint_page_projection_identity,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)
from projectkoios.ingestion.page.projection.publication.codec import (
    PageProjectionPublicationReceiptCodec,
)
from projectkoios.ingestion.page.projection.publication.error import (
    PageProjectionPublicationError,
    PageProjectionPublicationFailureReason,
)
from projectkoios.ingestion.page.projection.publication.receipt import (
    PageProjectionPublicationReceipt,
)
from projectkoios.ingestion.page.projection.publication.request import (
    PageProjectionPublicationRequest,
)
from projectkoios.ingestion.page.projection.publication.result import (
    PageProjectionPublicationResult,
)
from projectkoios.ingestion.page.projection.publication.status import (
    PageProjectionPublicationDisposition,
)
from projectkoios.ingestion.page.projection.publication.store import (
    PageProjectionPublicationJournal,
    PageProjectionPublicationStore,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash

DiskJsonObject = dict[str, JsonValue]


class DiskPageProjectionPublicationStore(PageProjectionPublicationStore):
    """Persist one trusted scope with atomic subject state as authority."""

    __slots__ = ("root", "_scope_id")

    IMPLEMENTATION_ID = "disk-page-projection-publication-store:1.0"

    def __init__(self, *, root: Path, deployment_scope_id: str) -> None:
        if not isinstance(root, Path):
            raise TypeError("root must be a Path")
        if (
            type(deployment_scope_id) is not str
            or not deployment_scope_id
            or len(deployment_scope_id.encode("utf-8", errors="strict")) > 512
        ):
            raise ValueError("deployment_scope_id is invalid")
        expanded = root.expanduser()
        if len(os.fsencode(expanded)) > 4_096:
            raise ValueError("publication store root exceeds its limit")
        if expanded.is_symlink():
            raise ValueError("publication store root cannot be a symlink")
        try:
            resolved = expanded.resolve(strict=True)
        except OSError:
            raise ValueError("publication store root is unavailable") from None
        if not resolved.is_dir():
            raise ValueError("publication store root must be a directory")
        self.root = resolved
        self._scope_id = fingerprint_page_projection_identity(
            namespace="page-projection-publication-store-scope",
            material={
                "deployment_scope_id": deployment_scope_id,
                "store_implementation_id": self.IMPLEMENTATION_ID,
            },
        )
        for name in ("locks", "objects", "receipts", "subjects"):
            directory = self.root / name
            directory.mkdir(mode=0o700, exist_ok=True)
            if directory.is_symlink() or not directory.is_dir():
                raise ValueError("publication store directory is unsafe")

    @property
    def implementation_id(self) -> str:
        """Return the exact disk store implementation identity."""
        return self.IMPLEMENTATION_ID

    @property
    def scope_id(self) -> str:
        """Return the immutable trusted publication scope identity."""
        return self._scope_id

    def open_journal(
        self, *, source_artifact_id: str
    ) -> AbstractContextManager[PageProjectionPublicationJournal]:
        """Lock and open one source subject journal."""
        PAGE_PROJECTION_LIMITS.require_identity(
            source_artifact_id, "source_artifact_id"
        )
        return open_disk_page_projection_publication_journal(
            root=self.root,
            scope_id=self.scope_id,
            source_artifact_id=source_artifact_id,
        )


class DiskPageProjectionPublicationJournal(PageProjectionPublicationJournal):
    """Operate one already-locked disk subject journal."""

    __slots__ = ("idempotency_scope_id", "root", "source_artifact_id")

    def __init__(
        self,
        *,
        root: Path,
        scope_id: str,
        source_artifact_id: str,
    ) -> None:
        self.root = root
        self.source_artifact_id = source_artifact_id
        self.idempotency_scope_id = fingerprint_page_projection_identity(
            namespace="page-projection-publication-idempotency-scope",
            material={
                "source_artifact_id": source_artifact_id,
                "store_scope_id": scope_id,
            },
        )

    def replay(
        self, *, request: PageProjectionPublicationRequest
    ) -> PageProjectionPublicationResult | None:
        """Return the exact committed receipt before any CAS evaluation."""
        state = read_disk_publication_state(
            root=self.root,
            source_artifact_id=self.source_artifact_id,
        )
        if state is None:
            return None
        entries = require_disk_json_object(state.get("idempotency"))
        token_digest = fingerprint_disk_idempotency_token(
            request.idempotency_token
        )
        raw_entry = entries.get(token_digest)
        if raw_entry is None:
            return None
        entry = require_disk_json_object(raw_entry)
        if (
            entry.get("request_fingerprint") != request.request_fingerprint
            or entry.get("request_id") != request.request_id
        ):
            raise PageProjectionPublicationError(
                reason=(
                    PageProjectionPublicationFailureReason.IDEMPOTENCY_CONFLICT
                ),
                message="idempotency token is committed to another request",
            )
        receipt_id = require_disk_string(entry.get("receipt_id"))
        return read_disk_publication_result(
            root=self.root,
            idempotency_scope_id=self.idempotency_scope_id,
            request_id=request.request_id,
            receipt_id=receipt_id,
            disposition=(
                PageProjectionPublicationDisposition.REPLAYED_IDENTICAL
            ),
        )

    def require_current(
        self, *, request: PageProjectionPublicationRequest
    ) -> None:
        """Require the exact current head declared by the request."""
        state = read_disk_publication_state(
            root=self.root,
            source_artifact_id=self.source_artifact_id,
        )
        observed = (
            None if state is None else state.get("current_publication_id")
        )
        if observed != request.expected_current_publication_id:
            raise PageProjectionPublicationError(
                reason=(
                    PageProjectionPublicationFailureReason.STALE_CURRENT_PUBLICATION
                ),
                message="expected publication head is stale",
            )

    def commit(
        self,
        *,
        request: PageProjectionPublicationRequest,
        receipt: PageProjectionPublicationReceipt,
        payload: bytes,
    ) -> PageProjectionPublicationResult:
        """Commit content objects and atomically advance subject authority."""
        if type(receipt) is not PageProjectionPublicationReceipt:
            raise TypeError("receipt has an unsupported type")
        if type(payload) is not bytes or not payload:
            raise TypeError("payload must be non-empty immutable bytes")
        self.require_current(request=request)
        replay = self.replay(request=request)
        if replay is not None:
            return replay
        payload_digest = SHA256Fingerprinter.fingerprint(content=payload)
        if (
            payload_digest != receipt.payload_sha256
            or len(payload) != receipt.payload_byte_length
        ):
            raise PageProjectionPublicationError(
                reason=(
                    PageProjectionPublicationFailureReason.PUBLICATION_INTEGRITY_INVALID
                ),
                message="private payload differs from its receipt",
            )
        body = (
            PageProjectionPublicationReceiptCodec()
            .encode(receipt=receipt)
            .encode("utf-8", errors="strict")
        )
        receipt_digest = SHA256Fingerprinter.fingerprint(content=body)
        receipt_id = (
            "page-projection-publication-receipt:sha256:" + receipt_digest
        )
        payload_path = disk_content_path(
            root=self.root,
            collection="objects",
            digest=payload_digest,
        )
        receipt_path = disk_content_path(
            root=self.root,
            collection="receipts",
            digest=receipt_digest,
        )
        write_disk_content_once(path=payload_path, content=payload)
        write_disk_content_once(path=receipt_path, content=body)
        state = read_disk_publication_state(
            root=self.root,
            source_artifact_id=self.source_artifact_id,
        )
        entries: DiskJsonObject = {}
        if state is not None:
            entries.update(require_disk_json_object(state.get("idempotency")))
        if len(entries) >= 4_096:
            raise PageProjectionPublicationError(
                reason=(
                    PageProjectionPublicationFailureReason.RESOURCE_LIMIT_EXCEEDED
                ),
                message="subject idempotency entries exceed their bound",
            )
        token_digest = fingerprint_disk_idempotency_token(
            request.idempotency_token
        )
        entries[token_digest] = {
            "receipt_id": receipt_id,
            "request_fingerprint": request.request_fingerprint,
            "request_id": request.request_id,
        }
        next_state: DiskJsonObject = {
            "contract_name": "disk-page-projection-publication-subject",
            "contract_version": "1.0",
            "current_publication_id": receipt.publication_id,
            "idempotency": entries,
            "source_artifact_id": self.source_artifact_id,
        }
        write_disk_publication_state(
            root=self.root,
            source_artifact_id=self.source_artifact_id,
            state=next_state,
        )
        committed = read_disk_publication_state(
            root=self.root,
            source_artifact_id=self.source_artifact_id,
        )
        if (
            committed is None
            or committed.get("current_publication_id") != receipt.publication_id
        ):
            raise PageProjectionPublicationError(
                reason=(
                    PageProjectionPublicationFailureReason.PUBLICATION_STORE_UNAVAILABLE
                ),
                message="publication state could not be confirmed",
            )
        return read_disk_publication_result(
            root=self.root,
            idempotency_scope_id=self.idempotency_scope_id,
            request_id=request.request_id,
            receipt_id=receipt_id,
            disposition=PageProjectionPublicationDisposition.CREATED,
        )


@contextmanager
def open_disk_page_projection_publication_journal(
    *, root: Path, scope_id: str, source_artifact_id: str
) -> Iterator[PageProjectionPublicationJournal]:
    """Hold one advisory subject lock across replay, CAS, and commit."""
    subject_digest = SHA256Fingerprinter.fingerprint(
        content=source_artifact_id.encode("utf-8", errors="strict")
    )
    lock_path = root / "locks" / f"{subject_digest}.lock"
    descriptor = os.open(
        lock_path,
        os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
    )
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield DiskPageProjectionPublicationJournal(
            root=root,
            scope_id=scope_id,
            source_artifact_id=source_artifact_id,
        )
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def fingerprint_disk_idempotency_token(token: str) -> str:
    """Return a safe state key without persisting the opaque caller token."""
    return SHA256Fingerprinter.fingerprint(
        content=token.encode("utf-8", errors="strict")
    )


def disk_subject_path(*, root: Path, source_artifact_id: str) -> Path:
    """Return the digest-only authority state path for one source subject."""
    digest = SHA256Fingerprinter.fingerprint(
        content=source_artifact_id.encode("utf-8", errors="strict")
    )
    return root / "subjects" / f"{digest}.json"


def disk_content_path(*, root: Path, collection: str, digest: str) -> Path:
    """Return one sharded digest-only immutable content path."""
    if collection not in {"objects", "receipts"}:
        raise ValueError("content collection is unsupported")
    if not SHA256Hash.is_canonical(digest):
        raise ValueError("content digest is not canonical")
    directory = root / collection / digest[:2]
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or not directory.is_dir():
        raise PageProjectionPublicationError(
            reason=(
                PageProjectionPublicationFailureReason.PUBLICATION_STORE_UNAVAILABLE
            ),
            message="publication content directory is unsafe",
        )
    return directory / f"{digest}.json"


def read_disk_publication_state(
    *, root: Path, source_artifact_id: str
) -> DiskJsonObject | None:
    """Read and validate one authoritative subject state object."""
    path = disk_subject_path(root=root, source_artifact_id=source_artifact_id)
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise PageProjectionPublicationError(
            reason=(
                PageProjectionPublicationFailureReason.PUBLICATION_STORE_UNAVAILABLE
            ),
            message="publication state is unavailable",
        ) from error
    try:
        value = JsonParser(CanonicalJsonSerializer.limits).parse_bytes(content)
    except ValueError as error:
        raise PageProjectionPublicationError(
            reason=(
                PageProjectionPublicationFailureReason.PUBLICATION_INTEGRITY_INVALID
            ),
            message="publication state is malformed",
        ) from error
    state = require_disk_json_object(value)
    if (
        state.get("contract_name") != "disk-page-projection-publication-subject"
        or state.get("contract_version") != "1.0"
        or state.get("source_artifact_id") != source_artifact_id
        or CanonicalJsonSerializer.serialize_bytes(state) != content
    ):
        raise PageProjectionPublicationError(
            reason=(
                PageProjectionPublicationFailureReason.PUBLICATION_INTEGRITY_INVALID
            ),
            message="publication state is inconsistent",
        )
    require_disk_json_object(state.get("idempotency"))
    current = state.get("current_publication_id")
    if current is not None and (
        type(current) is not str
        or not current.startswith("page-projection-publication:sha256:")
    ):
        raise PageProjectionPublicationError(
            reason=(
                PageProjectionPublicationFailureReason.PUBLICATION_INTEGRITY_INVALID
            ),
            message="publication state head is invalid",
        )
    return state


def write_disk_publication_state(
    *, root: Path, source_artifact_id: str, state: DiskJsonObject
) -> None:
    """Atomically replace and sync one complete subject authority state."""
    content = CanonicalJsonSerializer.serialize_bytes(state)
    path = disk_subject_path(root=root, source_artifact_id=source_artifact_id)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
        )
        try:
            write_disk_descriptor(descriptor=descriptor, content=content)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, path)
        sync_disk_directory(path.parent)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise PageProjectionPublicationError(
            reason=(
                PageProjectionPublicationFailureReason.PUBLICATION_STORE_UNAVAILABLE
            ),
            message="publication state commit failed",
        ) from error


def write_disk_content_once(*, path: Path, content: bytes) -> None:
    """Create immutable content or require exact existing equivalence."""
    try:
        existing = path.read_bytes()
    except FileNotFoundError:
        existing = None
    except OSError as error:
        raise PageProjectionPublicationError(
            reason=(
                PageProjectionPublicationFailureReason.PUBLICATION_STORE_UNAVAILABLE
            ),
            message="publication content is unavailable",
        ) from error
    if existing is not None:
        if existing != content:
            raise PageProjectionPublicationError(
                reason=(
                    PageProjectionPublicationFailureReason.PUBLICATION_COLLISION
                ),
                message="content-addressed publication object differs",
            )
        return
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
        )
        try:
            write_disk_descriptor(descriptor=descriptor, content=content)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            if path.read_bytes() != content:
                raise PageProjectionPublicationError(
                    reason=(
                        PageProjectionPublicationFailureReason.PUBLICATION_COLLISION
                    ),
                    message="concurrent publication content differs",
                ) from None
        sync_disk_directory(path.parent)
    except PageProjectionPublicationError:
        raise
    except OSError as error:
        raise PageProjectionPublicationError(
            reason=(
                PageProjectionPublicationFailureReason.PUBLICATION_STORE_UNAVAILABLE
            ),
            message="publication content write failed",
        ) from error
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def read_disk_publication_result(
    *,
    root: Path,
    idempotency_scope_id: str,
    request_id: str,
    receipt_id: str,
    disposition: PageProjectionPublicationDisposition,
) -> PageProjectionPublicationResult:
    """Reread and verify receipt plus private payload before returning."""
    prefix = "page-projection-publication-receipt:sha256:"
    if not receipt_id.startswith(prefix):
        raise PageProjectionPublicationError(
            reason=(
                PageProjectionPublicationFailureReason.PUBLICATION_INTEGRITY_INVALID
            ),
            message="committed receipt identity is invalid",
        )
    receipt_digest = SHA256Hash(receipt_id.removeprefix(prefix))
    receipt_path = disk_content_path(
        root=root, collection="receipts", digest=receipt_digest
    )
    try:
        body = receipt_path.read_bytes()
    except OSError as error:
        raise PageProjectionPublicationError(
            reason=(
                PageProjectionPublicationFailureReason.PUBLICATION_INTEGRITY_INVALID
            ),
            message="committed receipt is unavailable",
        ) from error
    if SHA256Fingerprinter.fingerprint(content=body) != receipt_digest:
        raise PageProjectionPublicationError(
            reason=(
                PageProjectionPublicationFailureReason.PUBLICATION_INTEGRITY_INVALID
            ),
            message="committed receipt digest differs",
        )
    try:
        text = body.decode("utf-8", errors="strict")
        receipt = PageProjectionPublicationReceiptCodec().decode(body_json=text)
    except (UnicodeError, TypeError, ValueError) as error:
        raise PageProjectionPublicationError(
            reason=(
                PageProjectionPublicationFailureReason.PUBLICATION_INTEGRITY_INVALID
            ),
            message="committed receipt is malformed",
        ) from error
    publication_id = receipt.publication_id
    payload_digest = receipt.payload_sha256
    payload_length = receipt.payload_byte_length
    payload_path = disk_content_path(
        root=root, collection="objects", digest=payload_digest
    )
    try:
        payload = payload_path.read_bytes()
    except OSError as error:
        raise PageProjectionPublicationError(
            reason=(
                PageProjectionPublicationFailureReason.PUBLICATION_INTEGRITY_INVALID
            ),
            message="committed private payload is unavailable",
        ) from error
    if (
        len(payload) != payload_length
        or SHA256Fingerprinter.fingerprint(content=payload) != payload_digest
    ):
        raise PageProjectionPublicationError(
            reason=(
                PageProjectionPublicationFailureReason.PUBLICATION_INTEGRITY_INVALID
            ),
            message="committed private payload differs",
        )
    return PageProjectionPublicationResult(
        disposition=disposition,
        idempotency_scope_id=idempotency_scope_id,
        request_id=request_id,
        receipt_id=receipt_id,
        receipt_sha256=receipt_digest,
        receipt_byte_length=len(body),
        receipt_body_json=text,
        committed_publication_id=publication_id,
    )


def require_disk_json_object(value: JsonValue | None) -> DiskJsonObject:
    """Return one exact JSON object or fail publication integrity."""
    if not isinstance(value, dict):
        raise PageProjectionPublicationError(
            reason=(
                PageProjectionPublicationFailureReason.PUBLICATION_INTEGRITY_INVALID
            ),
            message="publication journal object is malformed",
        )
    return value


def require_disk_string(value: JsonValue | None) -> str:
    """Return one bounded non-empty journal string."""
    if (
        type(value) is not str
        or not value
        or len(value.encode("utf-8", errors="strict")) > 4_096
    ):
        raise PageProjectionPublicationError(
            reason=(
                PageProjectionPublicationFailureReason.PUBLICATION_INTEGRITY_INVALID
            ),
            message="publication journal string is malformed",
        )
    return value


def write_disk_descriptor(*, descriptor: int, content: bytes) -> None:
    """Write all exact bytes to one already-open descriptor."""
    view = memoryview(content)
    written = 0
    while written < len(view):
        count = os.write(descriptor, view[written:])
        if count <= 0:
            raise OSError("publication descriptor write made no progress")
        written += count


def sync_disk_directory(path: Path) -> None:
    """Sync one directory after a durable link or rename operation."""
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
