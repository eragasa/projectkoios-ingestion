from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

import pytest
from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.artifact.managed.media.type import (
    ManagedArtifactMediaType,
)
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.artifact.managed.verification.actionizer import (
    ManagedArtifactVerificationActionizer,
)
from projectkoios.ingestion.artifact.managed.verification.error import (
    ManagedArtifactVerificationError,
)
from projectkoios.ingestion.artifact.managed.verification.evidence import (
    ManagedArtifactVerificationEvidenceInventory,
)
from projectkoios.ingestion.artifact.managed.verification.provider import (
    ManagedArtifactByteProvider,
)
from projectkoios.ingestion.artifact.managed.verification.request import (
    ManagedArtifactVerificationRequest,
)
from projectkoios.ingestion.integrations.disk.artifact.managed.binding import (
    DiskManagedArtifactBinding,
    DiskManagedArtifactBindingInventory,
)
from projectkoios.ingestion.integrations.disk.artifact.managed.provider import (
    DiskManagedArtifactByteProvider,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash

_AUTHORITY_ID = "test-managed-artifact-authority"


class OversizedChunkProvider(ManagedArtifactByteProvider):
    """Deliberately violate the neutral chunk contract for one gate test."""

    def __init__(self, content: bytes) -> None:
        self.content = content

    @property
    def implementation_id(self) -> str:
        return "oversized-chunk-provider:1.0"

    def open_chunks(
        self,
        *,
        reference: ManagedArtifactReference,
        authority_id: str,
        maximum_bytes: int,
        chunk_bytes: int,
    ) -> AbstractContextManager[Iterator[bytes]]:
        return nullcontext(iter((self.content,)))


def _reference(
    content: bytes, media_type: ManagedArtifactMediaType
) -> ManagedArtifactReference:
    return ManagedArtifactReference(
        sha256=SHA256Fingerprinter.fingerprint(content=content),
        byte_length=len(content),
        media_type=media_type,
    )


def _request(
    references: ManagedArtifactReferenceInventory,
) -> ManagedArtifactVerificationRequest:
    return ManagedArtifactVerificationRequest(
        references=references,
        provider_implementation_id=(
            DiskManagedArtifactByteProvider.IMPLEMENTATION_ID
        ),
        authority_id=_AUTHORITY_ID,
        maximum_artifact_bytes=max(
            (reference.byte_length for reference in references), default=1
        ),
        maximum_aggregate_bytes=max(references.aggregate_byte_length, 1),
        stream_chunk_bytes=3,
    )


def _provider(
    root: Path,
    bindings: list[DiskManagedArtifactBinding],
) -> DiskManagedArtifactByteProvider:
    return DiskManagedArtifactByteProvider(
        root=root,
        bindings=DiskManagedArtifactBindingInventory(
            *sorted(bindings, key=lambda value: value.artifact_id)
        ),
        authority_id=_AUTHORITY_ID,
    )


def test__managed_artifact_verification__covers_pdf_and_visual_bytes(
    tmp_path: Path,
) -> None:
    pdf = b"%PDF-1.7\nprivate source\n%%EOF\n"
    png = b"\x89PNG\r\n\x1a\nvisual-evidence"
    (tmp_path / "source.pdf").write_bytes(pdf)
    visual_directory = tmp_path / "visuals"
    visual_directory.mkdir()
    (visual_directory / "figure.png").write_bytes(png)
    pdf_reference = _reference(pdf, ManagedArtifactMediaType.APPLICATION_PDF)
    png_reference = _reference(png, ManagedArtifactMediaType.IMAGE_PNG)
    references = ManagedArtifactReferenceInventory(
        *sorted(
            (pdf_reference, png_reference),
            key=lambda value: value.artifact_id,
        )
    )
    provider = _provider(
        tmp_path,
        [
            DiskManagedArtifactBinding(
                artifact_id=pdf_reference.artifact_id,
                relative_path="source.pdf",
            ),
            DiskManagedArtifactBinding(
                artifact_id=png_reference.artifact_id,
                relative_path="visuals/figure.png",
            ),
        ],
    )

    result = ManagedArtifactVerificationActionizer(provider=provider).action(
        request=_request(references)
    )

    assert len(result.evidence) == 2
    assert result.evidence.aggregate_observed_byte_length == len(pdf) + len(png)
    for reference in references:
        observation = result.evidence.require(reference.artifact_id)
        assert observation.reference == reference
        assert observation.observed_sha256 == reference.sha256
        assert observation.observed_byte_length == reference.byte_length
        assert observation.observed_media_type is reference.media_type
        assert not hasattr(observation, "content")
        assert not hasattr(observation, "path")
    assert not hasattr(result, "content")


def test__managed_artifact_verification__rejects_digest_mismatch(
    tmp_path: Path,
) -> None:
    content = b"\x89PNG\r\n\x1a\nvisual-evidence"
    (tmp_path / "figure.png").write_bytes(content)
    reference = ManagedArtifactReference(
        sha256=SHA256Hash("a" * 64),
        byte_length=len(content),
        media_type=ManagedArtifactMediaType.IMAGE_PNG,
    )
    references = ManagedArtifactReferenceInventory(reference)
    provider = _provider(
        tmp_path,
        [
            DiskManagedArtifactBinding(
                artifact_id=reference.artifact_id,
                relative_path="figure.png",
            )
        ],
    )

    with pytest.raises(
        ManagedArtifactVerificationError, match="differ"
    ) as captured:
        ManagedArtifactVerificationActionizer(provider=provider).action(
            request=_request(references)
        )

    assert captured.value.code == "artifact_bytes_differ"


def test__managed_artifact_verification__rejects_media_signature_mismatch(
    tmp_path: Path,
) -> None:
    content = b"\x89PNG\r\n\x1a\nvisual-evidence"
    (tmp_path / "artifact.bin").write_bytes(content)
    reference = _reference(content, ManagedArtifactMediaType.APPLICATION_PDF)
    references = ManagedArtifactReferenceInventory(reference)
    provider = _provider(
        tmp_path,
        [
            DiskManagedArtifactBinding(
                artifact_id=reference.artifact_id,
                relative_path="artifact.bin",
            )
        ],
    )

    with pytest.raises(ManagedArtifactVerificationError) as captured:
        ManagedArtifactVerificationActionizer(provider=provider).action(
            request=_request(references)
        )

    assert captured.value.code == "media_type_differs"


def test__managed_artifact_verification__requires_exact_coverage(
    tmp_path: Path,
) -> None:
    first_content = b"%PDF-1.7\nfirst\n"
    second_content = b"\x89PNG\r\n\x1a\nsecond"
    (tmp_path / "first.pdf").write_bytes(first_content)
    (tmp_path / "second.png").write_bytes(second_content)
    first = _reference(first_content, ManagedArtifactMediaType.APPLICATION_PDF)
    second = _reference(second_content, ManagedArtifactMediaType.IMAGE_PNG)
    references = ManagedArtifactReferenceInventory(
        *sorted((first, second), key=lambda value: value.artifact_id)
    )
    provider = _provider(
        tmp_path,
        [
            DiskManagedArtifactBinding(first.artifact_id, "first.pdf"),
            DiskManagedArtifactBinding(second.artifact_id, "second.png"),
        ],
    )
    result = ManagedArtifactVerificationActionizer(provider=provider).action(
        request=_request(references)
    )
    first_evidence = tuple(result.evidence)[0]

    with pytest.raises(ValueError, match="exactly cover"):
        ManagedArtifactVerificationEvidenceInventory(references, first_evidence)
    with pytest.raises(ValueError, match="unique"):
        ManagedArtifactVerificationEvidenceInventory(
            references, first_evidence, first_evidence
        )


def test__managed_artifact_verification__enforces_provider_chunk_bound() -> (
    None
):
    content = b"%PDF-1.7\nsource\n"
    reference = _reference(content, ManagedArtifactMediaType.APPLICATION_PDF)
    references = ManagedArtifactReferenceInventory(reference)
    request = ManagedArtifactVerificationRequest(
        references=references,
        provider_implementation_id="oversized-chunk-provider:1.0",
        authority_id=_AUTHORITY_ID,
        maximum_artifact_bytes=len(content),
        maximum_aggregate_bytes=len(content),
        stream_chunk_bytes=3,
    )

    with pytest.raises(ManagedArtifactVerificationError) as captured:
        ManagedArtifactVerificationActionizer(
            provider=OversizedChunkProvider(content)
        ).action(request=request)

    assert captured.value.code == "provider_chunk_limit_exceeded"


def test__disk_managed_artifact_provider__rejects_missing_binding(
    tmp_path: Path,
) -> None:
    content = b"%PDF-1.7\nsource\n"
    reference = _reference(content, ManagedArtifactMediaType.APPLICATION_PDF)
    provider = _provider(tmp_path, [])

    with pytest.raises(ManagedArtifactVerificationError) as captured:
        ManagedArtifactVerificationActionizer(provider=provider).action(
            request=_request(ManagedArtifactReferenceInventory(reference))
        )

    assert captured.value.code == "artifact_binding_missing"


def test__disk_managed_artifact_provider__rejects_missing_file(
    tmp_path: Path,
) -> None:
    content = b"%PDF-1.7\nsource\n"
    reference = _reference(content, ManagedArtifactMediaType.APPLICATION_PDF)
    provider = _provider(
        tmp_path,
        [DiskManagedArtifactBinding(reference.artifact_id, "missing.pdf")],
    )

    with pytest.raises(ManagedArtifactVerificationError) as captured:
        ManagedArtifactVerificationActionizer(provider=provider).action(
            request=_request(ManagedArtifactReferenceInventory(reference))
        )

    assert captured.value.code == "artifact_unavailable"


def test__disk_managed_artifact_provider__rejects_symlink(
    tmp_path: Path,
) -> None:
    content = b"%PDF-1.7\nsource\n"
    target = tmp_path / "target.pdf"
    target.write_bytes(content)
    (tmp_path / "linked.pdf").symlink_to(target)
    reference = _reference(content, ManagedArtifactMediaType.APPLICATION_PDF)
    provider = _provider(
        tmp_path,
        [DiskManagedArtifactBinding(reference.artifact_id, "linked.pdf")],
    )

    with pytest.raises(ManagedArtifactVerificationError) as captured:
        ManagedArtifactVerificationActionizer(provider=provider).action(
            request=_request(ManagedArtifactReferenceInventory(reference))
        )

    assert captured.value.code == "unsafe_artifact_path"


def test__disk_managed_artifact_provider__rejects_intermediate_symlink(
    tmp_path: Path,
) -> None:
    content = b"%PDF-1.7\nsource\n"
    actual_directory = tmp_path / "actual"
    actual_directory.mkdir()
    (actual_directory / "source.pdf").write_bytes(content)
    (tmp_path / "linked").symlink_to(actual_directory, target_is_directory=True)
    reference = _reference(content, ManagedArtifactMediaType.APPLICATION_PDF)
    provider = _provider(
        tmp_path,
        [
            DiskManagedArtifactBinding(
                reference.artifact_id, "linked/source.pdf"
            )
        ],
    )

    with pytest.raises(ManagedArtifactVerificationError) as captured:
        ManagedArtifactVerificationActionizer(provider=provider).action(
            request=_request(ManagedArtifactReferenceInventory(reference))
        )

    assert captured.value.code == "unsafe_artifact_path"


def test__disk_managed_artifact_provider__rejects_nonregular_file(
    tmp_path: Path,
) -> None:
    fifo = tmp_path / "artifact.fifo"
    os.mkfifo(fifo)
    content = b"%PDF-1.7\nsource\n"
    reference = _reference(content, ManagedArtifactMediaType.APPLICATION_PDF)
    provider = _provider(
        tmp_path,
        [DiskManagedArtifactBinding(reference.artifact_id, "artifact.fifo")],
    )

    with pytest.raises(ManagedArtifactVerificationError) as captured:
        ManagedArtifactVerificationActionizer(provider=provider).action(
            request=_request(ManagedArtifactReferenceInventory(reference))
        )

    assert captured.value.code == "unsafe_artifact_path"


def test__disk_managed_artifact_provider__rejects_file_over_exact_bound(
    tmp_path: Path,
) -> None:
    expected = b"%PDF-1.7\n"
    actual = expected + b"unexpected"
    (tmp_path / "source.pdf").write_bytes(actual)
    reference = _reference(expected, ManagedArtifactMediaType.APPLICATION_PDF)
    provider = _provider(
        tmp_path,
        [DiskManagedArtifactBinding(reference.artifact_id, "source.pdf")],
    )

    with pytest.raises(ManagedArtifactVerificationError) as captured:
        ManagedArtifactVerificationActionizer(provider=provider).action(
            request=_request(ManagedArtifactReferenceInventory(reference))
        )

    assert captured.value.code == "artifact_byte_limit_exceeded"


def test__disk_managed_artifact_provider__enforces_authority(
    tmp_path: Path,
) -> None:
    content = b"%PDF-1.7\nsource\n"
    (tmp_path / "source.pdf").write_bytes(content)
    reference = _reference(content, ManagedArtifactMediaType.APPLICATION_PDF)
    provider = _provider(
        tmp_path,
        [DiskManagedArtifactBinding(reference.artifact_id, "source.pdf")],
    )
    request = ManagedArtifactVerificationRequest(
        references=ManagedArtifactReferenceInventory(reference),
        provider_implementation_id=provider.implementation_id,
        authority_id="different-authority",
        maximum_artifact_bytes=len(content),
        maximum_aggregate_bytes=len(content),
        stream_chunk_bytes=4,
    )

    with pytest.raises(ManagedArtifactVerificationError) as captured:
        ManagedArtifactVerificationActionizer(provider=provider).action(
            request=request
        )

    assert captured.value.code == "authority_differs"


@pytest.mark.parametrize(
    "relative_path",
    ("../source.pdf", "/source.pdf", "folder//source.pdf", "./source.pdf"),
)
def test__disk_managed_artifact_binding__rejects_unsafe_paths(
    relative_path: str,
) -> None:
    with pytest.raises(ValueError, match="root-relative"):
        DiskManagedArtifactBinding(
            artifact_id=f"managed-artifact:sha256:{'a' * 64}",
            relative_path=relative_path,
        )
