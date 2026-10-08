from dataclasses import FrozenInstanceError
from unittest.mock import Mock

import pytest
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.transcript.reading.evidence.association.evidence import (  # noqa: E501
    ReadingAssociationEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.association.role import (  # noqa: E501
    ReadingAssociationRole,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.label.inventory import (
    ReadingSourceLabelInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)
from projectkoios.ingestion.transcript.reading.evidence.span.evidence import (
    ReadingSourceSpanEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.span.geometry import (
    ReadingBoundingBox,
)
from projectkoios.ingestion.transcript.reading.evidence.span.inventory import (
    ReadingSourceSpanEvidenceInventory,
)

from .fixture import ReadingEvidenceFoundationFixture


def test__reading_evidence_identity__binds_role_and_grammar() -> None:
    identity = ReadingEvidenceIdentity(
        kind=ReadingEvidenceIdentityKind.DOCUMENT,
        value="document:sha256:" + "a" * 64,
    )

    assert identity.kind is ReadingEvidenceIdentityKind.DOCUMENT
    with pytest.raises(ReadingEvidenceError, match="invalid syntax"):
        ReadingEvidenceIdentity(
            kind=ReadingEvidenceIdentityKind.DOCUMENT,
            value="document with spaces",
        )


def test__reading_evidence_identity_inventory__rejects_another_role(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    source = reading_evidence_fixture.identity(
        ReadingEvidenceIdentityKind.SOURCE, "book"
    )

    with pytest.raises(ValueError, match="another role"):
        ReadingEvidenceIdentityInventory(
            ReadingEvidenceIdentityKind.DOCUMENT,
            source,
        )


def test__reading_page_location__is_deterministic_and_immutable() -> None:
    first = ReadingPageLocation(
        physical_page_index=0,
        printed_page_label="i",
    )
    second = ReadingPageLocation(
        physical_page_index=0,
        printed_page_label="i",
    )

    assert first == second
    assert first.physical_page_number == 1
    with pytest.raises(FrozenInstanceError):
        first.physical_page_index = 1  # type: ignore[misc]


def test__reading_evidence_limit_error__is_a_domain_failure() -> None:
    assert issubclass(ReadingEvidenceLimitError, ReadingEvidenceError)


def test__reading_page_location__validates_before_hashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fingerprint = Mock(side_effect=AssertionError("hashing must not run"))
    monkeypatch.setattr(SHA256Fingerprinter, "fingerprint", fingerprint)

    with pytest.raises(ReadingEvidenceLimitError):
        ReadingPageLocation(
            physical_page_index=0,
            printed_page_label="x" * 16_385,
        )

    fingerprint.assert_not_called()


def test__reading_bounding_box__rejects_invalid_geometry() -> None:
    with pytest.raises(ValueError, match="normalized"):
        ReadingBoundingBox(2.0, 0.0, 1.0, 1.0)
    with pytest.raises(ValueError, match="positive area"):
        ReadingBoundingBox(0.2, 0.0, 0.1, 1.0)


def test__reading_source_span__requires_paired_offsets(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    with pytest.raises(ValueError, match="supplied together"):
        ReadingSourceSpanEvidence(
            source_id=reading_evidence_fixture.identity(
                ReadingEvidenceIdentityKind.SOURCE, "book"
            ),
            page_location=reading_evidence_fixture.page(),
            start_offset=0,
        )


def test__reading_source_span__retains_invalid_geometry_warning(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    warning_id = reading_evidence_fixture.identity(
        ReadingEvidenceIdentityKind.WARNING, "invalid-geometry"
    )

    span = ReadingSourceSpanEvidence(
        source_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.SOURCE, "book"
        ),
        page_location=reading_evidence_fixture.page(),
        bounding_box=None,
        geometry_warning_id=warning_id,
    )

    assert span.bounding_box is None
    assert span.geometry_warning_id == warning_id


def test__source_collections__preserve_declared_order(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    source_id = reading_evidence_fixture.identity(
        ReadingEvidenceIdentityKind.SOURCE, "book"
    )
    page = reading_evidence_fixture.page()
    first = ReadingSourceSpanEvidence(
        source_id=source_id,
        page_location=page,
        start_offset=0,
        end_offset=1,
    )
    second = ReadingSourceSpanEvidence(
        source_id=source_id,
        page_location=page,
        start_offset=2,
        end_offset=3,
    )

    spans = ReadingSourceSpanEvidenceInventory(second, first)
    labels = ReadingSourceLabelInventory("second", "first")

    assert list(spans) == [second, first]
    assert list(labels) == ["second", "first"]


def test__reading_association__binds_exact_source_text(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    page = reading_evidence_fixture.page()
    source_object_id = reading_evidence_fixture.identity(
        ReadingEvidenceIdentityKind.SOURCE_OBJECT, "caption"
    )
    span = ReadingSourceSpanEvidence(
        source_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.SOURCE, "book"
        ),
        page_location=page,
        source_object_id=source_object_id,
    )
    block_ids = ReadingEvidenceIdentityInventory(
        ReadingEvidenceIdentityKind.SOURCE_BLOCK,
        reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.SOURCE_BLOCK, "caption"
        ),
    )

    association = ReadingAssociationEvidence(
        role=ReadingAssociationRole.CAPTION,
        text="Figure title",
        source_block_ids=block_ids,
        source_spans=ReadingSourceSpanEvidenceInventory(span),
        producer_association_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.ASSOCIATION, "upstream"
        ),
    )

    assert association.text == "Figure title"
    assert association.role is ReadingAssociationRole.CAPTION
