"""Exact current clean-transcript transformation derivation."""

from __future__ import annotations

import re

from projectkoios.ingestion.clean_transcript import (
    CleanTranscript,
    CleanTranscriptBlock,
    DehyphenationOutcome,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.transformation.definition import (  # noqa: E501
    ReadingTextTransformation,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.transformation.inventory import (  # noqa: E501
    ReadingTextTransformationInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.transformation.kind import (  # noqa: E501
    ReadingTextTransformationKind,
)

_SANITATION = re.compile(r"[\s\u00ad\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+")
_GLYPH_SUBSTITUTION = re.compile(r"[\u00ad\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
type _TransformationToken = tuple[
    int,
    int,
    str,
    ReadingTextTransformationKind | None,
    str | None,
]


def derive_reading_clean_text_transformations(
    *,
    block: CleanTranscriptBlock,
    transcript: CleanTranscript,
) -> ReadingTextTransformationInventory:
    """Derive replayable raw-coordinate edits from current clean evidence."""
    if type(block) is not CleanTranscriptBlock:
        raise TypeError("block must be CleanTranscriptBlock")
    if type(transcript) is not CleanTranscript:
        raise TypeError("transcript must be CleanTranscript")
    decisions_by_id = {
        value.decision_id: value for value in transcript.dehyphenation_decisions
    }
    decisions = tuple(
        sorted(
            (
                decisions_by_id[value]
                for value in block.dehyphenation_decision_ids
            ),
            key=lambda value: value.start_offset,
        )
    )
    if any(
        current.start_offset < previous.end_offset
        for previous, current in zip(decisions, decisions[1:], strict=False)
    ):
        raise ReadingEvidenceError("clean-text decisions overlap")

    tokens: list[_TransformationToken] = []
    raw = block.raw_text

    def append_gap(start: int, end: int) -> None:
        cursor = start
        for match in _SANITATION.finditer(raw, start, end):
            if cursor < match.start():
                tokens.append(
                    (
                        cursor,
                        match.start(),
                        raw[cursor : match.start()],
                        None,
                        None,
                    )
                )
            fragment = match.group()
            has_glyph_substitution = (
                _GLYPH_SUBSTITUTION.search(fragment) is not None
            )
            kind = (
                ReadingTextTransformationKind.GLYPH_SUBSTITUTION
                if has_glyph_substitution
                else ReadingTextTransformationKind.WHITESPACE_NORMALIZATION
            )
            rule_id = (
                "current-clean-transcript-sanitization-v2"
                if has_glyph_substitution
                else "current-clean-transcript-whitespace-v2"
            )
            tokens.append(
                (
                    match.start(),
                    match.end(),
                    " " if any(value != "\u00ad" for value in fragment) else "",
                    kind,
                    rule_id,
                )
            )
            cursor = match.end()
        if cursor < end:
            tokens.append((cursor, end, raw[cursor:end], None, None))

    cursor = 0
    for decision in decisions:
        if decision.start_offset < cursor or decision.end_offset > len(raw):
            raise ReadingEvidenceError("clean-text decision exceeds raw text")
        append_gap(cursor, decision.start_offset)
        if decision.outcome is DehyphenationOutcome.JOIN:
            replacement = decision.left_fragment + decision.right_fragment
        elif decision.outcome is DehyphenationOutcome.PRESERVE_HYPHEN:
            replacement = f"{decision.left_fragment}-{decision.right_fragment}"
        elif decision.outcome is (
            DehyphenationOutcome.PRESERVE_BREAK_CONSERVATIVELY
        ):
            replacement = f"{decision.left_fragment}- {decision.right_fragment}"
        else:
            raise ReadingEvidenceError(
                "clean-text decision has no current replay rule"
            )
        tokens.append(
            (
                decision.start_offset,
                decision.end_offset,
                replacement,
                ReadingTextTransformationKind.DEHYPHENATION,
                decision.rule_id,
            )
        )
        cursor = decision.end_offset
    append_gap(cursor, len(raw))

    visible = tuple(bool(value.strip()) for _, _, value, _, _ in tokens)
    transformations: list[ReadingTextTransformation] = []
    for index, (start, end, replacement, kind, rule_id) in enumerate(tokens):
        if (
            kind
            in (
                ReadingTextTransformationKind.WHITESPACE_NORMALIZATION,
                ReadingTextTransformationKind.GLYPH_SUBSTITUTION,
            )
            and replacement == " "
        ):
            replacement = (
                " "
                if any(visible[:index]) and any(visible[index + 1 :])
                else ""
            )
        if kind is None or raw[start:end] == replacement:
            continue
        assert rule_id is not None
        transformations.append(
            ReadingTextTransformation(
                kind=kind,
                source_start_offset=start,
                source_end_offset=end,
                replacement_text=replacement,
                rule_id=rule_id,
            )
        )
    result = ReadingTextTransformationInventory(*transformations)
    if result.apply(raw) != block.clean_text:
        raise ReadingEvidenceError(
            "current clean-text evidence cannot be replayed exactly"
        )
    return result
