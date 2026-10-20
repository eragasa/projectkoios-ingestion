"""Exact typed loading of immutable page-projection publications."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import cast

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
from projectkoios.ingestion.integrations.disk.page.projection.publication.load.runtime import (  # noqa: E501
    DiskPageProjectionPublicationLoadRuntime,
)
from projectkoios.ingestion.integrations.disk.page.projection.publication.load.source import (  # noqa: E501
    read_immutable_publication_object,
)
from projectkoios.ingestion.integrations.disk.page.projection.publication.runtime import (  # noqa: E501
    DiskPageProjectionPublicationRuntime,
)
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.json.error import JsonParseError
from projectkoios.ingestion.page.projection.enrichment.result import (
    PageProjectionEvidenceEnrichmentResult,
)
from projectkoios.ingestion.page.projection.publication.codec import (
    PageProjectionPublicationReceiptCodec,
)
from projectkoios.ingestion.page.projection.publication.configuration import (
    PageProjectionPublicationConfiguration,
)
from projectkoios.ingestion.page.projection.publication.load.codec import (
    PageProjectionPublicationPayloadCodec,
)
from projectkoios.ingestion.page.projection.publication.load.error import (
    PageProjectionPublicationLoadError,
    PageProjectionPublicationLoadFailureReason,
)
from projectkoios.ingestion.page.projection.publication.load.request import (
    PageProjectionPublicationLoadRequest,
)
from projectkoios.ingestion.page.projection.publication.request import (
    PageProjectionPublicationRequest,
)
from projectkoios.ingestion.page.projection.publication.result import (
    PageProjectionPublicationResult,
)
from projectkoios.ingestion.page.projection.publication.status import (
    PageProjectionPublicationProfile,
)
from projectkoios.ingestion.page.projection.result import PageProjectionResult
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash

pymupdf = pytest.importorskip("pymupdf")


def make_pdf(*, text: str = "Sanitized current evidence paragraph.") -> bytes:
    """Return one generated sanitized PDF without a repository byte fixture."""
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    content = cast(bytes, document.tobytes())
    document.close()
    return content


def make_publication_runtime(
    *,
    source_root: Path,
    publication_root: Path,
    reference: ManagedArtifactReference,
    low_text_character_threshold: int = 40,
) -> DiskPageProjectionPublicationRuntime:
    """Compose one reviewed publication runtime for a sanitized source."""
    return DiskPageProjectionPublicationRuntime(
        source_root=source_root,
        source_bindings=DiskManagedArtifactBindingInventory(
            DiskManagedArtifactBinding(
                artifact_id=reference.artifact_id,
                relative_path="sanitized.pdf",
            )
        ),
        publication_root=publication_root,
        deployment_scope_id="typed-loader-test",
        configuration=PageProjectionPublicationConfiguration(
            profile=PageProjectionPublicationProfile.NATIVE_PDF_TEXT_V1,
            authority_id="typed-loader-test-owner",
            maximum_page_count=10,
            maximum_block_count=100,
            maximum_payload_bytes=10_000_000,
            low_text_character_threshold=low_text_character_threshold,
        ),
    )


def publish(
    *,
    runtime: DiskPageProjectionPublicationRuntime,
    reference: ManagedArtifactReference,
    token: str,
    expected_current_publication_id: str | None = None,
) -> PageProjectionPublicationResult:
    """Publish one sanitized fixture through the reviewed owner action."""
    actionizer = runtime.create_actionizer()
    request = PageProjectionPublicationRequest(
        source_artifact=reference,
        expected_pipeline_configuration_id=(
            actionizer.pipeline_configuration_id
        ),
        maximum_page_count=1,
        maximum_block_count=10,
        idempotency_token=token,
        expected_current_publication_id=expected_current_publication_id,
    )
    return actionizer.action(request=request)


def make_load_request(
    *,
    reference: ManagedArtifactReference,
    receipt_body_json: str,
    receipt_id: str,
    receipt_sha256: SHA256Hash,
    receipt_byte_length: int,
    expected_page_projection_result_id: str | None = None,
) -> PageProjectionPublicationLoadRequest:
    """Bind one full immutable receipt to an exact typed-load request."""
    receipt = PageProjectionPublicationReceiptCodec().decode(
        body_json=receipt_body_json
    )
    return PageProjectionPublicationLoadRequest(
        source_artifact=reference,
        expected_pipeline_configuration_id=(receipt.pipeline_configuration_id),
        expected_publication_id=receipt.publication_id,
        expected_receipt_id=receipt_id,
        expected_receipt_sha256=receipt_sha256,
        expected_receipt_byte_length=receipt_byte_length,
        expected_payload_id=receipt.payload_id,
        expected_payload_sha256=receipt.payload_sha256,
        expected_payload_byte_length=receipt.payload_byte_length,
        expected_page_projection_result_id=(
            receipt.page_projection_result_id
            if expected_page_projection_result_id is None
            else expected_page_projection_result_id
        ),
        expected_enrichment_result_id=receipt.enrichment_result_id,
        maximum_payload_bytes=10_000_000,
    )


def fixture_publication(
    tmp_path: Path,
) -> tuple[
    ManagedArtifactReference,
    DiskPageProjectionPublicationRuntime,
    PageProjectionPublicationResult,
    PageProjectionPublicationLoadRequest,
]:
    """Create one sanitized immutable publication and load request."""
    content = make_pdf()
    source_root = tmp_path / "source"
    publication_root = tmp_path / "publication"
    source_root.mkdir()
    publication_root.mkdir()
    (source_root / "sanitized.pdf").write_bytes(content)
    reference = ManagedArtifactReference(
        sha256=SHA256Fingerprinter.fingerprint(content=content),
        byte_length=len(content),
        media_type=ManagedArtifactMediaType.APPLICATION_PDF,
    )
    runtime = make_publication_runtime(
        source_root=source_root,
        publication_root=publication_root,
        reference=reference,
    )
    created = publish(
        runtime=runtime,
        reference=reference,
        token="typed-load-1",
    )
    request = make_load_request(
        reference=reference,
        receipt_body_json=created.receipt_body_json,
        receipt_id=created.receipt_id,
        receipt_sha256=created.receipt_sha256,
        receipt_byte_length=created.receipt_byte_length,
    )
    return reference, runtime, created, request


def test__PageProjectionPublicationLoad__returns_exact_types_and_replays(
    tmp_path: Path,
) -> None:
    reference, _runtime, created, request = fixture_publication(tmp_path)
    publication_root = tmp_path / "publication"
    before = tuple(
        (path.relative_to(publication_root), path.stat().st_size)
        for path in sorted(publication_root.rglob("*"))
    )
    actionizer = DiskPageProjectionPublicationLoadRuntime(
        publication_root=publication_root
    ).create_actionizer()

    first = actionizer.action(request=request)
    second = actionizer.action(request=request)

    after = tuple(
        (path.relative_to(publication_root), path.stat().st_size)
        for path in sorted(publication_root.rglob("*"))
    )
    assert first == second
    assert first.result_id == second.result_id
    assert type(first.projection) is PageProjectionResult
    assert type(first.enrichment) is PageProjectionEvidenceEnrichmentResult
    assert first.enrichment.request.projection is first.projection
    assert (
        first.projection.result_id == request.expected_page_projection_result_id
    )
    assert first.enrichment.result_id == request.expected_enrichment_result_id
    assert first.receipt.publication_id == created.committed_publication_id
    assert first.receipt.source_artifact_id == reference.artifact_id
    assert before == after
    mirror_root = tmp_path / "publication-mirror"
    shutil.copytree(publication_root, mirror_root)
    mirrored = (
        DiskPageProjectionPublicationLoadRuntime(publication_root=mirror_root)
        .create_actionizer()
        .action(request=request)
    )
    assert mirrored == first
    unsafe = {"root", "path", "locator", "content", "payload"}
    assert set(
        PageProjectionPublicationLoadRequest.__dataclass_fields__
    ).isdisjoint(unsafe)
    assert set(type(first).__dataclass_fields__).isdisjoint(unsafe)


def test__PageProjectionPublicationLoad__loads_older_immutable_publication(
    tmp_path: Path,
) -> None:
    reference, first_runtime, first, first_request = fixture_publication(
        tmp_path
    )
    source_root = tmp_path / "source"
    publication_root = tmp_path / "publication"
    second_runtime = make_publication_runtime(
        source_root=source_root,
        publication_root=publication_root,
        reference=reference,
        low_text_character_threshold=0,
    )
    second = publish(
        runtime=second_runtime,
        reference=reference,
        token="typed-load-2",
        expected_current_publication_id=first.committed_publication_id,
    )
    assert second.committed_publication_id != first.committed_publication_id

    loaded = (
        DiskPageProjectionPublicationLoadRuntime(
            publication_root=publication_root
        )
        .create_actionizer()
        .action(request=first_request)
    )

    assert loaded.receipt.publication_id == first.committed_publication_id
    assert loaded.receipt.publication_id != second.committed_publication_id


def test__PageProjectionPublicationLoad__fails_closed_on_payload_corruption(
    tmp_path: Path,
) -> None:
    _reference, _runtime, _created, request = fixture_publication(tmp_path)
    publication_root = tmp_path / "publication"
    digest = str(request.expected_payload_sha256)
    payload_path = publication_root / "objects" / digest[:2] / f"{digest}.json"
    content = payload_path.read_bytes()
    payload_path.write_bytes(content[:-1] + bytes([content[-1] ^ 1]))

    with pytest.raises(PageProjectionPublicationLoadError) as failure:
        DiskPageProjectionPublicationLoadRuntime(
            publication_root=publication_root
        ).create_actionizer().action(request=request)

    assert failure.value.reason is (
        PageProjectionPublicationLoadFailureReason.PAYLOAD_INTEGRITY_INVALID
    )


def test__PageProjectionPublicationLoad__rejects_schema_and_identity_drift(
    tmp_path: Path,
) -> None:
    _reference, _runtime, _created, request = fixture_publication(tmp_path)
    publication_root = tmp_path / "publication"
    digest = str(request.expected_payload_sha256)
    payload_path = publication_root / "objects" / digest[:2] / f"{digest}.json"
    content = payload_path.read_bytes()
    codec = PageProjectionPublicationPayloadCodec()
    value = json.loads(content)
    value["unknown"] = "rejected"
    unknown = CanonicalJsonSerializer.serialize_bytes(value)
    with pytest.raises(JsonParseError, match="fields differ"):
        codec.decode(payload=unknown)
    value.pop("unknown")
    value["enrichment"]["result_id"] = (
        "page-projection-evidence-enrichment-result:sha256:" + "0" * 64
    )
    drifted = CanonicalJsonSerializer.serialize_bytes(value)
    with pytest.raises(JsonParseError, match="identities differ"):
        codec.decode(payload=drifted)
    with pytest.raises(JsonParseError, match="noncanonical"):
        codec.decode(payload=content + b" ")


@pytest.mark.parametrize("replacement", ("root", "intermediate", "final"))
def test__PageProjectionPublicationLoad__rejects_path_replacement(
    tmp_path: Path,
    replacement: str,
) -> None:
    _reference, _runtime, _created, request = fixture_publication(tmp_path)
    publication_root = tmp_path / "publication"
    actionizer = DiskPageProjectionPublicationLoadRuntime(
        publication_root=publication_root
    ).create_actionizer()
    payload_digest = str(request.expected_payload_sha256)
    if replacement == "root":
        original = tmp_path / "publication-original"
        publication_root.rename(original)
        publication_root.symlink_to(original, target_is_directory=True)
    elif replacement == "intermediate":
        objects = publication_root / "objects"
        original = publication_root / "objects-original"
        objects.rename(original)
        objects.symlink_to(original, target_is_directory=True)
    else:
        payload = (
            publication_root
            / "objects"
            / payload_digest[:2]
            / f"{payload_digest}.json"
        )
        original = payload.with_suffix(".original")
        payload.rename(original)
        payload.symlink_to(original)

    with pytest.raises(PageProjectionPublicationLoadError) as failure:
        actionizer.action(request=request)

    assert failure.value.reason in {
        PageProjectionPublicationLoadFailureReason.RECEIPT_UNAVAILABLE,
        PageProjectionPublicationLoadFailureReason.PAYLOAD_UNAVAILABLE,
    }
    assert failure.value.__cause__ is None
    assert failure.value.__context__ is None
    assert str(publication_root) not in repr(failure.value)


def test__PageProjectionPublicationLoad__sanitizes_missing_object_graph(
    tmp_path: Path,
) -> None:
    _reference, _runtime, created, request = fixture_publication(tmp_path)
    publication_root = tmp_path / "publication"
    actionizer = DiskPageProjectionPublicationLoadRuntime(
        publication_root=publication_root
    ).create_actionizer()
    receipt_digest = str(created.receipt_sha256)
    receipt = (
        publication_root
        / "receipts"
        / receipt_digest[:2]
        / f"{receipt_digest}.json"
    )
    receipt.unlink()

    with pytest.raises(PageProjectionPublicationLoadError) as failure:
        actionizer.action(request=request)

    observed: set[int] = set()
    pending: list[BaseException] = [failure.value]
    rendered: list[str] = []
    while pending:
        current = pending.pop()
        if id(current) in observed:
            continue
        observed.add(id(current))
        rendered.extend((str(current), repr(current)))
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
    assert failure.value.reason is (
        PageProjectionPublicationLoadFailureReason.RECEIPT_UNAVAILABLE
    )
    assert len(observed) == 1
    assert all(str(publication_root) not in value for value in rendered)
    assert all("receipts" not in value for value in rendered)


def test__PageProjectionPublicationLoad__helper_rejects_noncanonical_digest(
    tmp_path: Path,
) -> None:
    publication_root = tmp_path / "publication"
    publication_root.mkdir()
    status = publication_root.stat(follow_symlinks=False)

    with pytest.raises(ValueError, match="digest is invalid"):
        read_immutable_publication_object(
            root=publication_root,
            root_device=status.st_dev,
            root_inode=status.st_ino,
            collection="objects",
            digest="0" * 63,
            expected_byte_length=1,
            maximum_bytes=1,
        )


def test__PageProjectionPublicationLoad__rejects_wrong_expected_projection(
    tmp_path: Path,
) -> None:
    reference, _runtime, created, _request = fixture_publication(tmp_path)
    wrong = make_load_request(
        reference=reference,
        receipt_body_json=created.receipt_body_json,
        receipt_id=created.receipt_id,
        receipt_sha256=created.receipt_sha256,
        receipt_byte_length=created.receipt_byte_length,
        expected_page_projection_result_id=(
            "page-projection-result:sha256:" + "0" * 64
        ),
    )

    with pytest.raises(PageProjectionPublicationLoadError) as failure:
        DiskPageProjectionPublicationLoadRuntime(
            publication_root=tmp_path / "publication"
        ).create_actionizer().action(request=wrong)

    assert failure.value.reason is (
        PageProjectionPublicationLoadFailureReason.RECEIPT_INTEGRITY_INVALID
    )
