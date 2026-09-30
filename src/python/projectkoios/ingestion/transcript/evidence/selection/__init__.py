"""Bounded clean-transcript evidence selection for downstream authoring."""

from projectkoios.ingestion.transcript.evidence.selection.contracts import (
    TranscriptEvidenceSelectionLimitError,
    TranscriptEvidenceSelectionOutcome,
    TranscriptEvidenceSelectionRequest,
    TranscriptEvidenceSelectionResult,
)
from projectkoios.ingestion.transcript.evidence.selection.evidence import (
    SelectedTranscriptBlockEvidence,
    SelectedTranscriptPageEvidence,
    TranscriptEvidenceMappingBasis,
)
from projectkoios.ingestion.transcript.evidence.selection.selector import (
    TranscriptEvidenceSelector,
)

__all__ = [
    "SelectedTranscriptBlockEvidence",
    "SelectedTranscriptPageEvidence",
    "TranscriptEvidenceMappingBasis",
    "TranscriptEvidenceSelectionLimitError",
    "TranscriptEvidenceSelectionOutcome",
    "TranscriptEvidenceSelectionRequest",
    "TranscriptEvidenceSelectionResult",
    "TranscriptEvidenceSelector",
]
