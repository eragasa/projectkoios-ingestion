"""Immutable completion manifest for one extraction migration phase."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.storage.extraction.journal.inventory import (
    ExtractionPublicationJournalInventory,
)
from projectkoios.ingestion.storage.extraction.journal.selection import (
    ExtractionPublicationSelectionInventory,
)
from projectkoios.ingestion.storage.extraction.materialization.evidence.inventory import (  # noqa: E501
    ExtractionProjectionMaterializationEvidenceInventory,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.kind import (  # noqa: E501
    ExtractionProjectionEquivalenceKind,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.result import (  # noqa: E501
    ExtractionProjectionInventoryEquivalenceResult,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.evidence import (  # noqa: E501
    ExtractionProjectionInventoryEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.expected import (  # noqa: E501
    ExpectedExtractionProjectionInventory,
)

_GIT_COMMIT = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True, slots=True, init=False)
class ExtractionProjectionMigrationCompletionManifest(
    AbstractImmutableDataObject
):
    """Bind all evidence required to call one migration phase complete."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"

    manifest_id: str = field(init=False)
    phase: str
    migration_plan_sha256: str
    source_repository_commit: str
    eligible_identity_sha256: str
    eligible_publication_request_sha256: str
    eligible_projection_ids_sha256: str
    eligible_publication_count: int
    selected_publication_inventory_id: str
    source_journal_inventory_id: str
    source_journal_record_count: int
    source_journal_head_sha256: str
    primary_expected_inventory_id: str
    primary_observed_inventory_id: str
    replay_materialization_inventory_id: str
    same_store_equivalence_result_id: str
    independent_expected_inventory_id: str
    independent_observed_inventory_id: str
    independent_equivalence_result_id: str
    contract_version: str = CONTRACT_VERSION

    def __init__(
        self,
        *,
        phase: str,
        migration_plan_sha256: str,
        source_repository_commit: str,
        eligible_identity_sha256: str,
        eligible_publication_request_sha256: str,
        eligible_projection_ids_sha256: str,
        eligible_publication_count: int,
        selected_publications: ExtractionPublicationSelectionInventory,
        source_journal_frozen: ExtractionPublicationJournalInventory,
        source_journal_rechecked: ExtractionPublicationJournalInventory,
        primary_expected: ExpectedExtractionProjectionInventory,
        primary_observed: ExtractionProjectionInventoryEvidence,
        replay_materialization: (
            ExtractionProjectionMaterializationEvidenceInventory
        ),
        same_store_equivalence: (
            ExtractionProjectionInventoryEquivalenceResult
        ),
        independent_expected: ExpectedExtractionProjectionInventory,
        independent_observed: ExtractionProjectionInventoryEvidence,
        independent_equivalence: (
            ExtractionProjectionInventoryEquivalenceResult
        ),
        contract_version: str = CONTRACT_VERSION,
    ) -> None:
        if contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported migration completion manifest")
        if type(phase) is not str or not phase or len(phase) > 128:
            raise ValueError("migration phase is invalid")
        for value in (
            migration_plan_sha256,
            eligible_identity_sha256,
            eligible_publication_request_sha256,
            eligible_projection_ids_sha256,
        ):
            if not SHA256Hash.is_canonical(value):
                raise ValueError("migration completion hash is invalid")
        if not _GIT_COMMIT.fullmatch(source_repository_commit):
            raise ValueError("source repository commit is invalid")
        if (
            type(eligible_publication_count) is not int
            or not 1 <= eligible_publication_count <= 10_000_000
        ):
            raise ValueError("eligible publication count is out of bounds")
        if (
            type(selected_publications)
            is not ExtractionPublicationSelectionInventory
            or selected_publications.publication_count
            != eligible_publication_count
            or selected_publications.request_ids_sha256
            != eligible_publication_request_sha256
        ):
            raise ValueError(
                "selected publications do not cover the eligible phase"
            )
        if (
            type(source_journal_frozen)
            is not ExtractionPublicationJournalInventory
            or type(source_journal_rechecked)
            is not ExtractionPublicationJournalInventory
        ):
            raise TypeError("source journal evidence is invalid")
        if source_journal_frozen != source_journal_rechecked:
            raise ValueError("source journal drifted during migration")
        if (
            selected_publications.source_journal_inventory_id
            != source_journal_frozen.inventory_id
        ):
            raise ValueError(
                "selected publications do not belong to the frozen journal"
            )
        if (
            source_journal_frozen.head_sha256 is None
            or selected_publications.last_sequence
            > source_journal_frozen.record_count
        ):
            raise ValueError(
                "source journal does not contain the selected phase"
            )
        if type(primary_expected) is not ExpectedExtractionProjectionInventory:
            raise TypeError("primary expected inventory is invalid")
        if type(primary_observed) is not ExtractionProjectionInventoryEvidence:
            raise TypeError("primary observed inventory is invalid")
        if (
            primary_expected.target_id != primary_observed.target_id
            or primary_expected.configuration_id
            != primary_observed.configuration_id
            or primary_expected.schema_id != primary_observed.schema_id
        ):
            raise ValueError("primary inventory scope differs")
        if (
            type(replay_materialization)
            is not ExtractionProjectionMaterializationEvidenceInventory
            or replay_materialization.target_id != primary_observed.target_id
        ):
            raise ValueError("same-store replay scope differs")
        if (
            replay_materialization.projection_count
            != eligible_publication_count
            or replay_materialization.projection_ids_sha256
            != eligible_projection_ids_sha256
        ):
            raise ValueError("same-store replay projection set differs")
        self._require_equivalence(
            result=same_store_equivalence,
            kind=ExtractionProjectionEquivalenceKind.SAME_STORE_REPLAY,
            expected_inventory_id=primary_expected.expected_inventory_id,
            observed_inventory_id=primary_observed.inventory_id,
            replay_inventory_id=replay_materialization.inventory_id,
        )
        if (
            type(independent_expected)
            is not ExpectedExtractionProjectionInventory
            or type(independent_observed)
            is not ExtractionProjectionInventoryEvidence
        ):
            raise TypeError("independent rebuild inventory is invalid")
        if independent_observed.target_id == primary_observed.target_id:
            raise ValueError("independent rebuild target is not independent")
        if (
            independent_expected.target_id != independent_observed.target_id
            or independent_expected.configuration_id
            != independent_observed.configuration_id
            or independent_expected.schema_id != independent_observed.schema_id
        ):
            raise ValueError("independent rebuild inventory scope differs")
        primary_content = tuple(
            item.inventory_id for item in primary_observed.collections
        )
        independent_expected_content = tuple(
            item.inventory_id for item in independent_expected.collections
        )
        if primary_content != independent_expected_content:
            raise ValueError(
                "independent expectation differs from primary content"
            )
        self._require_equivalence(
            result=independent_equivalence,
            kind=ExtractionProjectionEquivalenceKind.INDEPENDENT_REBUILD,
            expected_inventory_id=independent_expected.expected_inventory_id,
            observed_inventory_id=independent_observed.inventory_id,
            replay_inventory_id=None,
        )
        source_journal_head = source_journal_frozen.head_sha256
        assert source_journal_head is not None
        identity_values = (
            phase,
            migration_plan_sha256,
            source_repository_commit,
            eligible_identity_sha256,
            eligible_publication_request_sha256,
            eligible_projection_ids_sha256,
            eligible_publication_count,
            selected_publications.inventory_id,
            source_journal_frozen.inventory_id,
            source_journal_frozen.record_count,
            source_journal_head,
            primary_expected.expected_inventory_id,
            primary_observed.inventory_id,
            replay_materialization.inventory_id,
            same_store_equivalence.result_id,
            independent_expected.expected_inventory_id,
            independent_observed.inventory_id,
            independent_equivalence.result_id,
            contract_version,
        )
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "migration_plan_sha256", migration_plan_sha256)
        object.__setattr__(
            self, "source_repository_commit", source_repository_commit
        )
        object.__setattr__(
            self, "eligible_identity_sha256", eligible_identity_sha256
        )
        object.__setattr__(
            self,
            "eligible_publication_request_sha256",
            eligible_publication_request_sha256,
        )
        object.__setattr__(
            self,
            "eligible_projection_ids_sha256",
            eligible_projection_ids_sha256,
        )
        object.__setattr__(
            self, "eligible_publication_count", eligible_publication_count
        )
        object.__setattr__(
            self,
            "selected_publication_inventory_id",
            selected_publications.inventory_id,
        )
        object.__setattr__(
            self,
            "source_journal_inventory_id",
            source_journal_frozen.inventory_id,
        )
        object.__setattr__(
            self,
            "source_journal_record_count",
            source_journal_frozen.record_count,
        )
        object.__setattr__(
            self, "source_journal_head_sha256", source_journal_head
        )
        object.__setattr__(
            self,
            "primary_expected_inventory_id",
            primary_expected.expected_inventory_id,
        )
        object.__setattr__(
            self, "primary_observed_inventory_id", primary_observed.inventory_id
        )
        object.__setattr__(
            self,
            "replay_materialization_inventory_id",
            replay_materialization.inventory_id,
        )
        object.__setattr__(
            self,
            "same_store_equivalence_result_id",
            same_store_equivalence.result_id,
        )
        object.__setattr__(
            self,
            "independent_expected_inventory_id",
            independent_expected.expected_inventory_id,
        )
        object.__setattr__(
            self,
            "independent_observed_inventory_id",
            independent_observed.inventory_id,
        )
        object.__setattr__(
            self,
            "independent_equivalence_result_id",
            independent_equivalence.result_id,
        )
        object.__setattr__(self, "contract_version", contract_version)
        object.__setattr__(
            self,
            "manifest_id",
            stable_id(
                "extraction-projection-migration-completion-manifest",
                self.CONTRACT_VERSION,
                identity_values,
            ),
        )

    @staticmethod
    def _require_equivalence(
        *,
        result: ExtractionProjectionInventoryEquivalenceResult,
        kind: ExtractionProjectionEquivalenceKind,
        expected_inventory_id: str,
        observed_inventory_id: str,
        replay_inventory_id: str | None,
    ) -> None:
        if (
            type(result) is not ExtractionProjectionInventoryEquivalenceResult
            or not result.equivalent
            or result.kind is not kind
            or result.expected_inventory_id != expected_inventory_id
            or result.observed_inventory_id != observed_inventory_id
            or result.replay_materialization_inventory_id != replay_inventory_id
        ):
            raise ValueError("migration equivalence evidence is incomplete")
