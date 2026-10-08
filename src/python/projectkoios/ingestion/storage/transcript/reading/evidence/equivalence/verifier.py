"""Pure backend-neutral reading-evidence equivalence verification."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.storage.transcript.reading.evidence.equivalence.kind import (  # noqa: E501
    ReadingEvidenceEquivalenceKind,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.equivalence.mismatch import (  # noqa: E501
    ReadingEvidenceEquivalenceMismatch,
    ReadingEvidenceEquivalenceMismatchInventory,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.equivalence.request import (  # noqa: E501
    ReadingEvidenceEquivalenceRequest,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.equivalence.result import (  # noqa: E501
    ReadingEvidenceEquivalenceResult,
)


class ReadingEvidenceEquivalenceVerifier(
    DataObjectActionizer[
        ReadingEvidenceEquivalenceRequest,
        ReadingEvidenceEquivalenceResult,
    ]
):
    """Compare verified canonical results and optional replay evidence."""

    __slots__ = ()

    VERIFIER_ID = "reading-evidence-equivalence-verifier:1.0"

    def action(
        self, *, request: ReadingEvidenceEquivalenceRequest
    ) -> ReadingEvidenceEquivalenceResult:
        """Return exact technical differences in canonical lexical order."""
        if type(request) is not ReadingEvidenceEquivalenceRequest:
            raise TypeError("request has an unsupported type")
        reference = request.reference
        observed = request.observed
        mismatches: list[ReadingEvidenceEquivalenceMismatch] = []
        if reference.document != observed.document:
            mismatches.append(ReadingEvidenceEquivalenceMismatch.DOCUMENT)
        if reference.inventory != observed.inventory:
            mismatches.append(ReadingEvidenceEquivalenceMismatch.INVENTORY)
        if reference.projection_result_id != observed.projection_result_id:
            mismatches.append(
                ReadingEvidenceEquivalenceMismatch.PROJECTION_RESULT
            )
        if request.kind is ReadingEvidenceEquivalenceKind.SAME_STORE_REPLAY:
            reference_materialization = request.reference_materialization
            replay = request.replay_materialization
            if reference_materialization is None or replay is None:
                replay_outcome_differs = True
            else:
                replay_outcome_differs = (
                    reference_materialization.projection_id,
                    reference_materialization.target_id,
                    reference_materialization.configuration_id,
                    reference_materialization.projected_document_count,
                ) != (
                    replay.projection_id,
                    replay.target_id,
                    replay.configuration_id,
                    replay.projected_document_count,
                )
                reference_counts = {
                    value.collection: (
                        value.created_count + value.unchanged_count
                    )
                    for value in reference_materialization.collections
                }
                replay_outcome_differs = replay_outcome_differs or any(
                    value.created_count != 0
                    or value.unchanged_count
                    != reference_counts[value.collection]
                    for value in replay.collections
                )
            if replay_outcome_differs:
                mismatches.append(
                    ReadingEvidenceEquivalenceMismatch.REPLAY_OUTCOME
                )
        return ReadingEvidenceEquivalenceResult(
            request=request,
            mismatches=ReadingEvidenceEquivalenceMismatchInventory(
                *sorted(set(mismatches), key=lambda value: value.value)
            ),
            verifier_id=self.VERIFIER_ID,
        )
