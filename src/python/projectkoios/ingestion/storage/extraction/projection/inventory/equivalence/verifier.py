"""Pure extraction projection inventory equivalence verifier."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.kind import (  # noqa: E501
    ExtractionProjectionEquivalenceKind,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.mismatch import (  # noqa: E501
    ExtractionProjectionInventoryMismatch,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.request import (  # noqa: E501
    ExtractionProjectionInventoryEquivalenceRequest,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.result import (  # noqa: E501
    ExtractionProjectionInventoryEquivalenceResult,
)


class ExtractionProjectionInventoryEquivalenceVerifier(
    DataObjectActionizer[
        ExtractionProjectionInventoryEquivalenceRequest,
        ExtractionProjectionInventoryEquivalenceResult,
    ]
):
    """Compare expected and observed compact full-content evidence."""

    __slots__ = ()

    verifier_name = "extraction-projection-inventory-equivalence"
    verifier_version = "1.0"

    def action(
        self,
        *,
        request: ExtractionProjectionInventoryEquivalenceRequest,
    ) -> ExtractionProjectionInventoryEquivalenceResult:
        """Return a completed comparison with explicit stop disposition."""
        if type(request) is not ExtractionProjectionInventoryEquivalenceRequest:
            raise TypeError("equivalence request has the wrong contract")
        expected = request.expected
        observed = request.observed
        mismatches: list[ExtractionProjectionInventoryMismatch] = []
        if expected.target_id != observed.target_id:
            mismatches.append(ExtractionProjectionInventoryMismatch.TARGET)
        if expected.configuration_id != observed.configuration_id:
            mismatches.append(
                ExtractionProjectionInventoryMismatch.CONFIGURATION
            )
        if expected.schema_id != observed.schema_id:
            mismatches.append(ExtractionProjectionInventoryMismatch.SCHEMA)
        expected_by_name = {
            item.collection_name: item for item in expected.collections
        }
        if (
            request.kind
            is ExtractionProjectionEquivalenceKind.SAME_STORE_REPLAY
        ):
            replay = request.replay_materialization
            replay_configuration = request.replay_materialization_configuration
            expected_document_count = sum(
                item.document_count for item in expected.collections
            )
            replay_is_invalid = (
                replay is None
                or replay_configuration is None
                or replay.target_id != expected.target_id
                or replay.configuration_id
                != replay_configuration.configuration_id
                or replay_configuration.schema_id != expected.schema_id
                or replay.created_document_count != 0
                or replay.unchanged_document_count != expected_document_count
                or replay.projected_document_count != expected_document_count
            )
            if (
                replay is not None
                and replay_configuration is not None
                and not replay_is_invalid
            ):
                collection_counts = replay.collection_counts()
                expected_physical_names = {
                    replay_configuration.collection_name(collection)
                    for collection in collection_counts
                }
                replay_is_invalid = expected_physical_names != set(
                    expected_by_name
                ) or any(
                    created != 0
                    or unchanged
                    != expected_by_name[
                        replay_configuration.collection_name(collection)
                    ].document_count
                    for collection, (created, unchanged) in (
                        collection_counts.items()
                    )
                )
            if replay_is_invalid:
                mismatches.append(
                    ExtractionProjectionInventoryMismatch.REPLAY_MATERIALIZATION
                )
        observed_by_name = {
            item.collection_name: item for item in observed.collections
        }
        expected_names = set(expected_by_name)
        observed_names = set(observed_by_name)
        different_names = expected_names ^ observed_names
        if different_names:
            mismatches.append(
                ExtractionProjectionInventoryMismatch.COLLECTION_SET
            )
        changed_names = {
            name
            for name in expected_names & observed_names
            if expected_by_name[name].inventory_id
            != observed_by_name[name].inventory_id
        }
        if changed_names:
            mismatches.append(
                ExtractionProjectionInventoryMismatch.COLLECTION_CONTENT
            )
        return ExtractionProjectionInventoryEquivalenceResult.create(
            request=request,
            mismatches=tuple(sorted(mismatches)),
            mismatched_collection_names=tuple(
                sorted(different_names | changed_names)
            ),
            verifier_name=self.verifier_name,
            verifier_version=self.verifier_version,
        )
