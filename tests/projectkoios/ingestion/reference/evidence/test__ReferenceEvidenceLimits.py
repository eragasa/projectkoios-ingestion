from dataclasses import FrozenInstanceError

import pytest
from projectkoios.ingestion.reference.evidence.limits.definition import (
    REFERENCE_EVIDENCE_LIMITS,
    ReferenceEvidenceLimits,
)


def test__reference_evidence_limits__owns_fixed_immutable_bounds() -> None:
    limits = ReferenceEvidenceLimits()

    assert limits == REFERENCE_EVIDENCE_LIMITS
    assert limits.maximum_document_bytes == 262_144
    assert limits.maximum_identity_input_bytes == limits.maximum_document_bytes
    assert limits.maximum_bound_artifact_bytes == 128_000_000
    assert limits.maximum_lineage_identities == 4_096

    with pytest.raises(FrozenInstanceError):
        limits.maximum_document_bytes = 1  # type: ignore[misc]


def test__reference_evidence_limits__cannot_be_reconfigured() -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        ReferenceEvidenceLimits(  # type: ignore[call-arg]
            maximum_document_bytes=1
        )
