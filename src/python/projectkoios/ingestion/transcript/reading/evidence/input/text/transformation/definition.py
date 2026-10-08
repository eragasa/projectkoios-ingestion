"""Exact clean-text transformation definitions."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.derivation import (  # noqa: E501
    ReadingEvidenceIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.transformation.kind import (  # noqa: E501
    ReadingTextTransformationKind,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)


@dataclass(frozen=True, slots=True)
class ReadingTextTransformation:
    """Describe one ordered exact raw-to-clean text transformation."""

    kind: ReadingTextTransformationKind
    source_start_offset: int
    source_end_offset: int
    replacement_text: str
    rule_id: str
    transformation_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ReadingTextTransformationKind):
            raise TypeError("kind must be ReadingTextTransformationKind")
        start = READING_EVIDENCE_LIMITS.require_nonnegative_int(
            self.source_start_offset, "source_start_offset"
        )
        end = READING_EVIDENCE_LIMITS.require_nonnegative_int(
            self.source_end_offset, "source_end_offset"
        )
        if end < start:
            raise ReadingEvidenceError(
                "transformation source offsets must be ordered"
            )
        READING_EVIDENCE_LIMITS.require_string(
            self.replacement_text,
            "replacement_text",
            maximum_bytes=READING_EVIDENCE_LIMITS.maximum_block_text_bytes,
        )
        READING_EVIDENCE_LIMITS.require_text(
            self.rule_id,
            "rule_id",
            maximum_bytes=READING_EVIDENCE_LIMITS.maximum_rule_id_bytes,
        )
        object.__setattr__(
            self,
            "transformation_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.TRANSFORMATION,
                prefix="reading-text-transformation",
                material={
                    "kind": self.kind,
                    "source_start_offset": start,
                    "source_end_offset": end,
                    "replacement_text": self.replacement_text,
                    "rule_id": self.rule_id,
                },
            ),
        )
