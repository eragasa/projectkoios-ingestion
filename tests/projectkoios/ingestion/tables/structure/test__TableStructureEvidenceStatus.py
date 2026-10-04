"""Ownership and nominal-base checks for TableStructureEvidenceStatus."""

from enum import StrEnum

from projectkoios.ingestion.tables.structure.evidence_status import (
    TableStructureEvidenceStatus,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        TableStructureEvidenceStatus.__module__
        == "projectkoios.ingestion.tables.structure.evidence_status"
    )
    assert issubclass(TableStructureEvidenceStatus, StrEnum)
