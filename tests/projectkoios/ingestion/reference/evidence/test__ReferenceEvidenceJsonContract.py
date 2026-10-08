from __future__ import annotations

import json

import pytest
from projectkoios.ingestion.clean_transcript import CleanTranscriptStatus
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.reference.evidence.definition import (
    REFERENCE_EVIDENCE_CONTRACT_VERSION,
)
from projectkoios.ingestion.reference.evidence.error import (
    ReferenceEvidenceParseError,
    ReferenceEvidenceVerificationError,
)
from projectkoios.ingestion.reference.evidence.json.contract import (
    ReferenceEvidenceJsonContract,
)
from projectkoios.ingestion.reference.evidence.limits.definition import (
    REFERENCE_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.reference.evidence.limits.error import (
    ReferenceEvidenceLimitError,
)
from projectkoios.ingestion.reference.evidence.status import (
    ReferenceEvidenceCompleteness,
)

from tests.projectkoios.ingestion.reference.evidence.fixture.record import (
    ReferenceEvidenceRecordFixture,
)


def test__reference_evidence_json__fixture_is_canonical_and_addressed(
    reference_evidence_record_fixture: ReferenceEvidenceRecordFixture,
) -> None:
    contract = ReferenceEvidenceJsonContract()
    expected = (
        reference_evidence_record_fixture.fixture_directory / "complete.json"
    ).read_bytes()
    first = contract.serialize_bytes(
        reference_evidence_record_fixture.complete_record()
    )
    second = contract.serialize_bytes(
        reference_evidence_record_fixture.complete_record()
    )

    assert first == second == expected
    parsed = contract.parse_bytes(expected)
    assert parsed == reference_evidence_record_fixture.complete_record()
    assert parsed.contract_version == REFERENCE_EVIDENCE_CONTRACT_VERSION
    assert parsed.completeness is ReferenceEvidenceCompleteness.COMPLETE
    assert (
        parsed.transcript.status is CleanTranscriptStatus.AUTOMATED_UNREVIEWED
    )
    assert parsed.derivation_audit.independently_revalidated is False
    assert b"path" not in expected.lower()
    assert b"filename" not in expected.lower()
    assert b"workspace" not in expected.lower()


def test__reference_evidence_json__changed_record_changes_bytes(
    reference_evidence_record_fixture: ReferenceEvidenceRecordFixture,
) -> None:
    contract = ReferenceEvidenceJsonContract()
    original = reference_evidence_record_fixture.complete_record()
    value = contract.to_json_value(original)
    assert isinstance(value, dict)
    value["completeness"] = "incomplete"
    value["completeness_reasons"] = ["changed"]

    assert CanonicalJsonSerializer.serialize_bytes(value) != (
        contract.serialize_bytes(original)
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        # An extra root field proves the root schema is closed.
        pytest.param("unknown_root_field", "unknown fields", id="unknown-root"),
        # A removed generation key must not silently select a legacy shape.
        pytest.param(
            "removed_generation_key",
            "unknown fields",
            id="removed-generation",
        ),
        # A removed dependent contract key must remain unsupported.
        pytest.param(
            "removed_contract_key",
            "unknown fields",
            id="removed-contract",
        ),
        # A future contract version cannot be interpreted as version 0.1.0.
        pytest.param(
            "unsupported_version",
            "unsupported reference-evidence contract version",
            id="unsupported-version",
        ),
        # A trailing newline violates the compact canonical byte profile.
        pytest.param("noncanonical", "not canonical", id="noncanonical"),
        # Duplicate object fields must fail before typed reconstruction.
        pytest.param(
            "duplicate_field",
            "duplicate JSON object field",
            id="duplicate-field",
        ),
        # A failed recorded audit contradicts complete reusable evidence.
        pytest.param(
            "contradictory_audit",
            "requires a recorded passing audit",
            id="contradictory-audit",
        ),
    ),
)
def test__reference_evidence_json__strict_parse_rejects_mutation(
    mutation: str,
    message: str,
    reference_evidence_record_fixture: ReferenceEvidenceRecordFixture,
) -> None:
    contract = ReferenceEvidenceJsonContract()
    payload = (
        reference_evidence_record_fixture.fixture_directory / "complete.json"
    ).read_bytes()
    value = json.loads(payload)
    if mutation == "unknown_root_field":
        value["external"] = True
        payload = CanonicalJsonSerializer.serialize_text(value).encode()
    elif mutation == "removed_generation_key":
        value["transcript"]["artifact_generation"] = 1
        payload = CanonicalJsonSerializer.serialize_text(value).encode()
    elif mutation == "removed_contract_key":
        value["transcript"]["contract_version"] = "1.0"
        payload = CanonicalJsonSerializer.serialize_text(value).encode()
    elif mutation == "unsupported_version":
        value["contract_version"] = "0.2.0"
        payload = CanonicalJsonSerializer.serialize_text(value).encode()
    elif mutation == "noncanonical":
        payload += b"\n"
    elif mutation == "duplicate_field":
        payload = payload[:-1] + b',"schema_version":1}'
    elif mutation == "contradictory_audit":
        value["derivation_audit"]["status"] = "failed"
        payload = CanonicalJsonSerializer.serialize_text(value).encode()
    else:
        raise AssertionError(f"unsupported fixture mutation: {mutation}")

    with pytest.raises(ReferenceEvidenceParseError, match=message):
        contract.parse_bytes(payload)


def test__reference_evidence_json__incomplete_record_fails_parse(
    reference_evidence_record_fixture: ReferenceEvidenceRecordFixture,
) -> None:
    contract = ReferenceEvidenceJsonContract()
    complete = reference_evidence_record_fixture.complete_record()
    incomplete = reference_evidence_record_fixture.incomplete_record(
        original=complete,
        reason="consumer_fixture_deliberately_incomplete",
    )

    with pytest.raises(ReferenceEvidenceVerificationError, match="incomplete"):
        contract.parse_bytes(contract.serialize_bytes(incomplete))


def test__reference_evidence_json__malformed_input_fails_explicitly() -> None:
    with pytest.raises(ReferenceEvidenceParseError, match="malformed JSON"):
        ReferenceEvidenceJsonContract().parse_bytes(b'{"contract_id":')


def test__reference_evidence_json__oversized_input_fails_before_parse() -> None:
    with pytest.raises(ReferenceEvidenceLimitError, match="size limit"):
        ReferenceEvidenceJsonContract().parse_bytes(
            b" " * (REFERENCE_EVIDENCE_LIMITS.maximum_document_bytes + 1)
        )
