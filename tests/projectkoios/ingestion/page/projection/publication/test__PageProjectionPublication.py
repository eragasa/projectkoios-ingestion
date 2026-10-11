"""Durable owner lifecycle tests for page-projection publication."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from projectkoios.ingestion.artifact.managed.media.type import (
    ManagedArtifactMediaType,
)
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.integrations.disk.artifact.managed.binding import (
    DiskManagedArtifactBinding,
    DiskManagedArtifactBindingInventory,
)
from projectkoios.ingestion.integrations.disk.page.projection.publication.runtime import (  # noqa: E501
    DiskPageProjectionPublicationRuntime,
)
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.page.projection.publication import (
    actionizer as publication_actionizer_module,
)
from projectkoios.ingestion.page.projection.publication.codec import (
    PageProjectionPublicationReceiptCodec,
)
from projectkoios.ingestion.page.projection.publication.configuration import (
    PageProjectionPublicationConfiguration,
)
from projectkoios.ingestion.page.projection.publication.error import (
    PageProjectionPublicationError,
    PageProjectionPublicationFailureReason,
)
from projectkoios.ingestion.page.projection.publication.read.request import (
    PageProjectionPublicationReadRequest,
)
from projectkoios.ingestion.page.projection.publication.read.result import (
    PageProjectionPublicationReadResult,
)
from projectkoios.ingestion.page.projection.publication.read.status import (
    PageProjectionPublicationReadDisposition,
)
from projectkoios.ingestion.page.projection.publication.request import (
    PageProjectionPublicationRequest,
)
from projectkoios.ingestion.page.projection.publication.status import (
    PageProjectionPublicationDisposition,
    PageProjectionPublicationProfile,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

pymupdf = pytest.importorskip("pymupdf")


def make_pdf() -> bytes:
    """Return one small deterministic two-page native-text PDF."""
    document = pymupdf.open()
    first = document.new_page()
    first.insert_text((72, 72), "First current evidence paragraph.")
    second = document.new_page()
    second.insert_text((72, 72), "Second current evidence paragraph.")
    content = document.tobytes()
    document.close()
    return content


def make_runtime(
    *,
    source_root: Path,
    publication_root: Path,
    reference: ManagedArtifactReference,
    relative_path: str,
    deployment_scope_id: str = "test-private-development",
) -> DiskPageProjectionPublicationRuntime:
    """Build one trusted runtime without exposing paths to its request."""
    binding = DiskManagedArtifactBinding(
        artifact_id=reference.artifact_id,
        relative_path=relative_path,
    )
    return DiskPageProjectionPublicationRuntime(
        source_root=source_root,
        source_bindings=DiskManagedArtifactBindingInventory(binding),
        publication_root=publication_root,
        deployment_scope_id=deployment_scope_id,
        configuration=PageProjectionPublicationConfiguration(
            profile=PageProjectionPublicationProfile.NATIVE_PDF_TEXT_V1,
            authority_id="test-page-projection-publication-owner",
            maximum_page_count=100,
            maximum_block_count=10_000,
        ),
    )


def make_request(
    *,
    runtime: DiskPageProjectionPublicationRuntime,
    reference: ManagedArtifactReference,
    token: str,
    expected_current_publication_id: str | None = None,
    maximum_block_count: int = 100,
) -> PageProjectionPublicationRequest:
    """Build one owner-native request from safe exact artifact scalars."""
    actionizer = runtime.create_actionizer()
    return PageProjectionPublicationRequest(
        source_artifact=reference,
        expected_pipeline_configuration_id=(
            actionizer.pipeline_configuration_id
        ),
        maximum_page_count=10,
        maximum_block_count=maximum_block_count,
        idempotency_token=token,
        expected_current_publication_id=(expected_current_publication_id),
    )


def test__PageProjectionPublication__binds_inventory_ceiling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = make_pdf()
    source_root = tmp_path / "source"
    publication_root = tmp_path / "publication"
    source_root.mkdir()
    publication_root.mkdir()
    reference = ManagedArtifactReference(
        sha256=SHA256Fingerprinter.fingerprint(content=content),
        byte_length=len(content),
        media_type=ManagedArtifactMediaType.APPLICATION_PDF,
    )
    runtime = make_runtime(
        source_root=source_root,
        publication_root=publication_root,
        reference=reference,
        relative_path="opaque.pdf",
    )
    baseline = runtime.create_actionizer().pipeline_configuration_id

    monkeypatch.setattr(
        publication_actionizer_module,
        "READING_EVIDENCE_LIMITS",
        SimpleNamespace(maximum_records=1_000_001),
    )

    changed = runtime.create_actionizer().pipeline_configuration_id
    assert changed != baseline


def test__PageProjectionPublicationRead__absent_has_no_effect(
    tmp_path: Path,
) -> None:
    content = make_pdf()
    source_root = tmp_path / "source"
    publication_root = tmp_path / "publication"
    source_root.mkdir()
    publication_root.mkdir()
    reference = ManagedArtifactReference(
        sha256=SHA256Fingerprinter.fingerprint(content=content),
        byte_length=len(content),
        media_type=ManagedArtifactMediaType.APPLICATION_PDF,
    )
    runtime = make_runtime(
        source_root=source_root,
        publication_root=publication_root,
        reference=reference,
        relative_path="absent.pdf",
    )
    actionizer = runtime.create_read_actionizer()
    before = tuple(
        sorted(
            path.relative_to(publication_root)
            for path in publication_root.rglob("*")
        )
    )

    result = actionizer.action(
        request=PageProjectionPublicationReadRequest(
            source_artifact=reference
        )
    )

    after = tuple(
        sorted(
            path.relative_to(publication_root)
            for path in publication_root.rglob("*")
        )
    )
    assert result.disposition is PageProjectionPublicationReadDisposition.ABSENT
    assert result.source_artifact_id == reference.artifact_id
    assert result.current_publication_id is None
    assert result.receipt_id is None
    assert result.receipt_sha256 is None
    assert result.receipt_byte_length is None
    assert result.receipt_body_json is None
    assert after == before


def test__PageProjectionPublication__creates_and_replays_after_restart(
    tmp_path: Path,
) -> None:
    content = make_pdf()
    source_root = tmp_path / "source"
    publication_root = tmp_path / "publication"
    source_root.mkdir()
    publication_root.mkdir()
    source_path = source_root / "opaque.pdf"
    source_path.write_bytes(content)
    reference = ManagedArtifactReference(
        sha256=SHA256Fingerprinter.fingerprint(content=content),
        byte_length=len(content),
        media_type=ManagedArtifactMediaType.APPLICATION_PDF,
    )
    runtime = make_runtime(
        source_root=source_root,
        publication_root=publication_root,
        reference=reference,
        relative_path=source_path.name,
    )
    request = make_request(
        runtime=runtime,
        reference=reference,
        token="opaque-token-1",
    )

    created = runtime.create_actionizer().action(request=request)
    source_path.unlink()
    restarted_runtime = make_runtime(
        source_root=source_root,
        publication_root=publication_root,
        reference=reference,
        relative_path="opaque.pdf",
    )
    replayed = restarted_runtime.create_actionizer().action(request=request)

    assert created.disposition is PageProjectionPublicationDisposition.CREATED
    assert replayed.disposition is (
        PageProjectionPublicationDisposition.REPLAYED_IDENTICAL
    )
    assert replayed.receipt_id == created.receipt_id
    assert replayed.receipt_sha256 == created.receipt_sha256
    assert replayed.receipt_byte_length == created.receipt_byte_length
    assert replayed.receipt_body_json == created.receipt_body_json
    assert replayed.committed_publication_id == (
        created.committed_publication_id
    )

    current = restarted_runtime.create_read_actionizer().action(
        request=PageProjectionPublicationReadRequest(
            source_artifact=reference
        )
    )
    assert current.disposition is (
        PageProjectionPublicationReadDisposition.CURRENT
    )
    assert current.source_artifact_id == reference.artifact_id
    assert current.current_publication_id == created.committed_publication_id
    assert current.receipt_id == created.receipt_id
    assert current.receipt_sha256 == created.receipt_sha256
    assert current.receipt_byte_length == created.receipt_byte_length
    assert current.receipt_body_json == created.receipt_body_json

    codec = PageProjectionPublicationReceiptCodec()
    receipt = codec.decode(body_json=created.receipt_body_json)
    assert codec.encode(receipt=receipt) == created.receipt_body_json
    body = json.loads(created.receipt_body_json)
    assert body["source_sha256"] == reference.sha256
    assert body["source_artifact_id"] == reference.artifact_id
    assert body["page_count"] == 2
    assert body["block_count"] == 2
    assert body["enrichment_available_count"] == 2
    assert body["enrichment_unavailable_count"] == 0
    assert body["extraction_warning_codes"] == ["pdf.low_text_density"]
    assert body["reading_limitation_codes"] == []
    assert body["page_projection_limitation_codes"] == [
        "citation_acceptance_not_established",
        "claim_support_not_established",
        "proofreading_not_established",
        "publication_suitability_not_established",
        "rights_not_established",
        "scientific_validity_not_established",
    ]
    changed = dict(body)
    changed["private_path"] = "/private/source.pdf"
    changed_json = json.dumps(changed, separators=(",", ":"), sort_keys=True)
    with pytest.raises(ValueError, match="fields differ"):
        codec.decode(body_json=changed_json)
    assert not any(
        unsafe in key
        for key in body
        for unsafe in (
            "path",
            "locator",
            "bytes",
            "queue",
            "selection",
            "observation",
            "runtime_evidence",
            "source_asset",
        )
    )


def test__PageProjectionPublication__conflict_and_cas_precede_source_read(
    tmp_path: Path,
) -> None:
    content = make_pdf()
    source_root = tmp_path / "source"
    publication_root = tmp_path / "publication"
    source_root.mkdir()
    publication_root.mkdir()
    source_path = source_root / "book.pdf"
    source_path.write_bytes(content)
    reference = ManagedArtifactReference(
        sha256=SHA256Fingerprinter.fingerprint(content=content),
        byte_length=len(content),
        media_type=ManagedArtifactMediaType.APPLICATION_PDF,
    )
    runtime = make_runtime(
        source_root=source_root,
        publication_root=publication_root,
        reference=reference,
        relative_path=source_path.name,
    )
    first = make_request(
        runtime=runtime,
        reference=reference,
        token="same-token",
    )
    runtime.create_actionizer().action(request=first)
    source_path.unlink()

    conflicting = make_request(
        runtime=runtime,
        reference=reference,
        token="same-token",
        maximum_block_count=101,
    )
    with pytest.raises(PageProjectionPublicationError) as conflict:
        runtime.create_actionizer().action(request=conflicting)
    assert conflict.value.reason is (
        PageProjectionPublicationFailureReason.IDEMPOTENCY_CONFLICT
    )

    stale = make_request(
        runtime=runtime,
        reference=reference,
        token="new-token",
        expected_current_publication_id=None,
    )
    with pytest.raises(PageProjectionPublicationError) as stale_error:
        runtime.create_actionizer().action(request=stale)
    assert stale_error.value.reason is (
        PageProjectionPublicationFailureReason.STALE_CURRENT_PUBLICATION
    )


def test__PageProjectionPublicationRead__fails_closed_on_corruption(
    tmp_path: Path,
) -> None:
    content = make_pdf()
    source_root = tmp_path / "source"
    publication_root = tmp_path / "publication"
    source_root.mkdir()
    publication_root.mkdir()
    source_path = source_root / "book.pdf"
    source_path.write_bytes(content)
    reference = ManagedArtifactReference(
        sha256=SHA256Fingerprinter.fingerprint(content=content),
        byte_length=len(content),
        media_type=ManagedArtifactMediaType.APPLICATION_PDF,
    )
    runtime = make_runtime(
        source_root=source_root,
        publication_root=publication_root,
        reference=reference,
        relative_path=source_path.name,
    )
    created = runtime.create_actionizer().action(
        request=make_request(
            runtime=runtime,
            reference=reference,
            token="corruption-read-token",
        )
    )
    receipt_digest = str(created.receipt_sha256)
    receipt_path = (
        publication_root
        / "receipts"
        / receipt_digest[:2]
        / f"{receipt_digest}.json"
    )
    subject_paths = tuple((publication_root / "subjects").iterdir())
    state_path = subject_paths[0]
    state_before = state_path.read_bytes()
    state = json.loads(state_before)
    state["unexpected"] = "unsafe"
    state_path.write_bytes(CanonicalJsonSerializer.serialize_bytes(state))

    with pytest.raises(PageProjectionPublicationError) as state_failure:
        runtime.create_read_actionizer().action(
            request=PageProjectionPublicationReadRequest(
                source_artifact=reference
            )
        )
    assert state_failure.value.reason is (
        PageProjectionPublicationFailureReason.PUBLICATION_INTEGRITY_INVALID
    )

    state_path.write_bytes(state_before)
    receipt_path.write_bytes(b"{}")
    with pytest.raises(PageProjectionPublicationError) as receipt_failure:
        runtime.create_read_actionizer().action(
            request=PageProjectionPublicationReadRequest(
                source_artifact=reference
            )
        )
    assert receipt_failure.value.reason is (
        PageProjectionPublicationFailureReason.PUBLICATION_INTEGRITY_INVALID
    )
    assert state_path.read_bytes() == state_before


def test__PageProjectionPublication__content_identity_excludes_path_and_scope(
    tmp_path: Path,
) -> None:
    content = make_pdf()
    reference = ManagedArtifactReference(
        sha256=SHA256Fingerprinter.fingerprint(content=content),
        byte_length=len(content),
        media_type=ManagedArtifactMediaType.APPLICATION_PDF,
    )
    results = []
    for index, relative_path in enumerate(("first.pdf", "nested/second.pdf")):
        root = tmp_path / str(index)
        source_root = root / "source"
        publication_root = root / "publication"
        source_path = source_root / relative_path
        source_path.parent.mkdir(parents=True)
        publication_root.mkdir(parents=True)
        source_path.write_bytes(content)
        runtime = make_runtime(
            source_root=source_root,
            publication_root=publication_root,
            reference=reference,
            relative_path=relative_path,
            deployment_scope_id=f"test-scope-{index}",
        )
        request = make_request(
            runtime=runtime,
            reference=reference,
            token=f"token-{index}",
        )
        results.append(runtime.create_actionizer().action(request=request))

    assert results[0].receipt_body_json == results[1].receipt_body_json
    assert results[0].receipt_id == results[1].receipt_id
    assert results[0].committed_publication_id == (
        results[1].committed_publication_id
    )
    assert results[0].idempotency_scope_id != results[1].idempotency_scope_id


def test__PageProjectionPublication__request_excludes_external_authority() -> (
    None
):
    field_names = set(PageProjectionPublicationRequest.__dataclass_fields__)
    read_request_fields = set(
        PageProjectionPublicationReadRequest.__dataclass_fields__
    )
    read_result_fields = set(
        PageProjectionPublicationReadResult.__dataclass_fields__
    )

    assert field_names.isdisjoint(
        {
            "queue_id",
            "selection_id",
            "asset_observation_id",
            "runtime_evidence_id",
            "source_asset_id",
            "decision_id",
            "binding_id",
            "path",
            "content",
        }
    )
    unsafe_fields = {
        "queue_id",
        "selection_id",
        "asset_observation_id",
        "runtime_evidence_id",
        "source_asset_id",
        "decision_id",
        "binding_id",
        "path",
        "payload",
        "content",
    }
    assert read_request_fields.isdisjoint(unsafe_fields)
    assert read_result_fields.isdisjoint(unsafe_fields)
