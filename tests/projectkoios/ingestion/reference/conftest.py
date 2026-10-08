"""Explicit pytest fixtures for reference-domain tests."""

from pathlib import Path

import pytest

from tests.projectkoios.ingestion.reference.claim.fixture import (
    ReferenceClaimCandidateFixture,
)
from tests.projectkoios.ingestion.reference.evidence.fixture.projection import (
    ReferenceEvidenceProjectionFixture,
)
from tests.projectkoios.ingestion.reference.evidence.fixture.record import (
    ReferenceEvidenceRecordFixture,
)
from tests.projectkoios.ingestion.reference.page.location.fixture import (
    ReferencePageLocationFixture,
)


@pytest.fixture
def reference_evidence_projection_fixture() -> (
    ReferenceEvidenceProjectionFixture
):
    """Return the immutable producer-graph fixture owner."""
    return ReferenceEvidenceProjectionFixture()


@pytest.fixture
def reference_evidence_record_fixture(
    repository_root: Path,
) -> ReferenceEvidenceRecordFixture:
    """Return the immutable record scenario with injected fixture storage."""
    return ReferenceEvidenceRecordFixture(
        fixture_directory=(
            repository_root / "tests" / "fixtures" / "reference_evidence"
        )
    )


@pytest.fixture
def reference_page_location_fixture() -> ReferencePageLocationFixture:
    """Return one immutable page-location fixture owner."""
    return ReferencePageLocationFixture()


@pytest.fixture
def reference_claim_candidate_fixture(
    reference_evidence_projection_fixture: ReferenceEvidenceProjectionFixture,
) -> ReferenceClaimCandidateFixture:
    """Return one claim fixture bound to evidence projection inputs."""
    return ReferenceClaimCandidateFixture(reference_evidence_projection_fixture)
