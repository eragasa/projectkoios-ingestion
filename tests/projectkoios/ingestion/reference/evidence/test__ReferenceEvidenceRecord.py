from dataclasses import replace
from unittest.mock import patch

import pytest
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.reference.evidence.error import (
    ReferenceEvidenceVerificationError,
)
from projectkoios.ingestion.reference.evidence.identity import (
    ReferenceEvidenceRecordIdentityDerivation,
)
from projectkoios.ingestion.reference.evidence.limits.error import (
    ReferenceEvidenceLimitError,
)
from projectkoios.ingestion.reference.evidence.lineage import (
    ReferenceEvidenceAuditArtifactIdentityInventory,
)
from projectkoios.ingestion.reference.evidence.record import (
    ReferenceEvidenceRecord,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

from tests.projectkoios.ingestion.reference.evidence.fixture.record import (
    ReferenceEvidenceRecordFixture,
)


def test__reference_evidence_record__changed_evidence_changes_identity(
    reference_evidence_record_fixture: ReferenceEvidenceRecordFixture,
) -> None:
    original = reference_evidence_record_fixture.complete_record()
    changed_transcript = replace(
        original.transcript,
        text_sha256=SHA256Fingerprinter.fingerprint(
            content=b"changed transcript"
        ),
    )
    changed = reference_evidence_record_fixture.record_with_transcript(
        original=original,
        transcript=changed_transcript,
    )

    assert changed.record_id != original.record_id


def test__reference_evidence_record__incomplete_record_fails_reuse(
    reference_evidence_record_fixture: ReferenceEvidenceRecordFixture,
) -> None:
    complete = reference_evidence_record_fixture.complete_record()
    incomplete = reference_evidence_record_fixture.incomplete_record(
        original=complete,
        reason="consumer_fixture_deliberately_incomplete",
    )

    with pytest.raises(ReferenceEvidenceVerificationError, match="incomplete"):
        incomplete.require_reusable()


def test__reference_evidence_record__has_no_projection_bypass() -> None:
    assert not hasattr(ReferenceEvidenceRecord, "create")
    assert not hasattr(ReferenceEvidenceRecord, "identity_for")


def test__reference_evidence_record__requires_semantic_inventories(
    reference_evidence_record_fixture: ReferenceEvidenceRecordFixture,
) -> None:
    record = reference_evidence_record_fixture.complete_record()

    with pytest.raises(TypeError, match="semantic inventory"):
        replace(
            record.transcript,
            layout_result_ids=tuple(  # type: ignore[arg-type]
                record.transcript.layout_result_ids
            ),
        )
    with pytest.raises(TypeError, match="semantic inventory"):
        replace(
            record.derivation_audit,
            audited_artifact_ids=tuple(  # type: ignore[arg-type]
                record.derivation_audit.audited_artifact_ids
            ),
        )
    with pytest.raises(TypeError, match="semantic inventory"):
        replace(
            record,
            limitations=tuple(record.limitations),  # type: ignore[arg-type]
        )


def test__reference_evidence_record__rejects_before_identity_hashing(
    reference_evidence_record_fixture: ReferenceEvidenceRecordFixture,
) -> None:
    record = reference_evidence_record_fixture.complete_record()

    with patch(
        "projectkoios.ingestion.reference.evidence.identity."
        "SHA256Fingerprinter.fingerprint"
    ) as fingerprint:
        with pytest.raises(ValueError, match="contract ID"):
            replace(record, contract_id="unsupported")

    fingerprint.assert_not_called()


def test__reference_evidence_record__rejects_oversized_identity_before_hashing(
    reference_evidence_record_fixture: ReferenceEvidenceRecordFixture,
) -> None:
    record = reference_evidence_record_fixture.complete_record()
    required_identities = tuple(record.derivation_audit.audited_artifact_ids)
    oversized_identities = ReferenceEvidenceAuditArtifactIdentityInventory(
        *required_identities,
        *(f"extra-{index:04d}-" + ("x" * 4_080) for index in range(80)),
    )
    audit = replace(
        record.derivation_audit,
        audited_artifact_ids=oversized_identities,
    )
    derivation = ReferenceEvidenceRecordIdentityDerivation(
        contract_id=record.contract_id,
        contract_version=record.contract_version,
        contract_status=record.contract_status,
        schema_version=record.schema_version,
        media_type=record.media_type,
        generator_name=record.generator_name,
        generator_version=record.generator_version,
        completeness=record.completeness,
        completeness_reasons=record.completeness_reasons,
        source=record.source,
        extraction=record.extraction,
        transcript=record.transcript,
        derivation_audit=audit,
        limitations=record.limitations,
    )

    with patch(
        "projectkoios.ingestion.reference.evidence.identity."
        "SHA256Fingerprinter.fingerprint"
    ) as fingerprint:
        with pytest.raises(
            ReferenceEvidenceLimitError,
            match="identity input exceeds size limit",
        ):
            _ = derivation.value

    fingerprint.assert_not_called()


def test__reference_evidence_record__serializes_identity_material_once(
    reference_evidence_record_fixture: ReferenceEvidenceRecordFixture,
) -> None:
    record = reference_evidence_record_fixture.complete_record()
    derivation = ReferenceEvidenceRecordIdentityDerivation(
        contract_id=record.contract_id,
        contract_version=record.contract_version,
        contract_status=record.contract_status,
        schema_version=record.schema_version,
        media_type=record.media_type,
        generator_name=record.generator_name,
        generator_version=record.generator_version,
        completeness=record.completeness,
        completeness_reasons=record.completeness_reasons,
        source=record.source,
        extraction=record.extraction,
        transcript=record.transcript,
        derivation_audit=record.derivation_audit,
        limitations=record.limitations,
    )

    with patch.object(
        CanonicalJsonSerializer,
        "serialize_bytes",
        wraps=CanonicalJsonSerializer.serialize_bytes,
    ) as serialize:
        assert derivation.value == record.record_id

    serialize.assert_called_once()


def test__reference_evidence_record__requires_exact_wire_bound(
    reference_evidence_record_fixture: ReferenceEvidenceRecordFixture,
) -> None:
    record = reference_evidence_record_fixture.complete_record()

    with patch(
        "projectkoios.ingestion.reference.evidence.json.contract."
        "ReferenceEvidenceJsonContract.serialize_bytes",
        side_effect=ReferenceEvidenceLimitError("fixture wire limit"),
    ) as serialize:
        with pytest.raises(
            ReferenceEvidenceLimitError,
            match="fixture wire limit",
        ):
            replace(record)

    serialize.assert_called_once()
