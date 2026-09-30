"""Synthetic tests for bounded clean-transcript evidence selection."""

from __future__ import annotations

import hashlib
import importlib
from dataclasses import FrozenInstanceError, replace

import pytest
from projectkoios.base import (
    DataObjectActionizer,
    DataObjectActionRequest,
    DataObjectActionResult,
)
from projectkoios.ingestion import (
    CleanTranscript,
    CleanTranscriptBlock,
    CleanTranscriptPage,
    CleanTranscriptStatus,
    SelectedTranscriptBlockEvidence,
    SelectedTranscriptPageEvidence,
    TranscriptEvidenceMappingBasis,
    TranscriptEvidenceSelectionLimitError,
    TranscriptEvidenceSelectionOutcome,
    TranscriptEvidenceSelectionRequest,
    TranscriptEvidenceSelectionResult,
    TranscriptEvidenceSelector,
)
from projectkoios.ingestion.identity import stable_id

_TRANSFORMATIONS = (
    ("control_character_offsets", ""),
    ("dehyphenation_decision_count", "0"),
    ("soft_hyphen_offsets", ""),
    ("unicode_normalization", "none"),
    ("whitespace_normalization", "collapse_unicode_whitespace"),
)


def _block(
    *,
    block_id: str,
    page_index: int,
    printed_page_label: str,
    order_index: int,
    raw_text: str,
    clean_text: str,
) -> CleanTranscriptBlock:
    return CleanTranscriptBlock.create(
        block_id=block_id,
        page_index=page_index,
        printed_page_label=printed_page_label,
        order_index=order_index,
        raw_text=raw_text,
        clean_text=clean_text,
        source_spans=(),
        transformations=_TRANSFORMATIONS,
        dehyphenation_decision_ids=(),
        page_number_classification_id=None,
        publisher_classification_id=None,
        private_use_finding_ids=(),
    )


def _page(
    *, page_index: int, label: str, blocks: tuple[CleanTranscriptBlock, ...]
) -> CleanTranscriptPage:
    marker = f'[[PAGE physical={page_index + 1} printed="{label}"]]'
    body = "\n\n".join(block.clean_text for block in blocks)
    return CleanTranscriptPage.create(
        page_index=page_index,
        printed_page_label=label,
        block_record_ids=tuple(block.record_id for block in blocks),
        text=marker if not body else f"{marker}\n\n{body}",
    )


def _transcript(
    *,
    warnings: tuple[str, ...] = (),
    incomplete_page_membership: bool = False,
) -> CleanTranscript:
    blocks = (
        _block(
            block_id="root-block-a",
            page_index=0,
            printed_page_label="i",
            order_index=0,
            raw_text="Alpha-\n beta",
            clean_text="Alpha- beta",
        ),
        _block(
            block_id="root-block-b",
            page_index=0,
            printed_page_label="i",
            order_index=1,
            raw_text="Raw   spacing",
            clean_text="Raw spacing",
        ),
        _block(
            block_id="root-block-c",
            page_index=1,
            printed_page_label="2",
            order_index=2,
            raw_text="Third page raw",
            clean_text="Third page raw",
        ),
    )
    first_page_blocks = blocks[:1] if incomplete_page_membership else blocks[:2]
    pages = (
        _page(page_index=0, label="i", blocks=first_page_blocks),
        _page(page_index=1, label="2", blocks=blocks[2:]),
    )
    text = "\n\n".join(page.text for page in pages) + "\n"
    encoded = text.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    transcription_result_id = stable_id("fixture-transcription", "one")
    document_id = stable_id("fixture-document", "one")
    layout_result_ids = (stable_id("fixture-layout", "one"),)
    normalized_warnings = tuple(sorted(set(warnings)))
    result_id = stable_id(
        "clean-transcript-result",
        transcription_result_id,
        document_id,
        "fixture:transcript-evidence-selection",
        "blob:sha256:" + "a" * 64,
        "a" * 64,
        layout_result_ids,
        tuple(page.page_id for page in pages),
        tuple(block.record_id for block in blocks),
        (),
        (),
        (),
        (),
        (),
        digest,
        len(encoded),
        CleanTranscriptStatus.AUTOMATED_UNREVIEWED,
        normalized_warnings,
        "fixture-projector",
        "1",
        "fixture-configuration",
    )
    return CleanTranscript(
        result_id=result_id,
        transcription_result_id=transcription_result_id,
        document_id=document_id,
        source_id="fixture:transcript-evidence-selection",
        source_blob_id="blob:sha256:" + "a" * 64,
        source_content_hash="a" * 64,
        layout_result_ids=layout_result_ids,
        pages=pages,
        blocks=blocks,
        exclusions=(),
        dehyphenation_decisions=(),
        page_number_classifications=(),
        publisher_front_matter=(),
        private_use_glyph_findings=(),
        text=text,
        text_sha256=digest,
        utf8_byte_length=len(encoded),
        status=CleanTranscriptStatus.AUTOMATED_UNREVIEWED,
        warnings=normalized_warnings,
        processor_name="fixture-projector",
        processor_version="1",
        configuration_digest="fixture-configuration",
    )


def _request(
    transcript: CleanTranscript, ids: tuple[str, ...]
) -> TranscriptEvidenceSelectionRequest:
    return TranscriptEvidenceSelectionRequest(
        transcript=transcript,
        selected_block_record_ids=ids,
    )


def test__selection_api__canonical_owner_matches_root_facade() -> None:
    canonical = importlib.import_module(
        "projectkoios.ingestion.transcript.evidence.selection"
    )
    contracts = importlib.import_module(
        "projectkoios.ingestion.transcript.evidence.selection.contracts"
    )
    evidence = importlib.import_module(
        "projectkoios.ingestion.transcript.evidence.selection.evidence"
    )
    selector = importlib.import_module(
        "projectkoios.ingestion.transcript.evidence.selection.selector"
    )
    root_exports = {
        "SelectedTranscriptBlockEvidence": SelectedTranscriptBlockEvidence,
        "SelectedTranscriptPageEvidence": SelectedTranscriptPageEvidence,
        "TranscriptEvidenceMappingBasis": TranscriptEvidenceMappingBasis,
        "TranscriptEvidenceSelectionLimitError": (
            TranscriptEvidenceSelectionLimitError
        ),
        "TranscriptEvidenceSelectionOutcome": (
            TranscriptEvidenceSelectionOutcome
        ),
        "TranscriptEvidenceSelectionRequest": (
            TranscriptEvidenceSelectionRequest
        ),
        "TranscriptEvidenceSelectionResult": TranscriptEvidenceSelectionResult,
        "TranscriptEvidenceSelector": TranscriptEvidenceSelector,
    }

    defining_modules = {
        "SelectedTranscriptBlockEvidence": evidence,
        "SelectedTranscriptPageEvidence": evidence,
        "TranscriptEvidenceMappingBasis": evidence,
        "TranscriptEvidenceSelectionLimitError": contracts,
        "TranscriptEvidenceSelectionOutcome": contracts,
        "TranscriptEvidenceSelectionRequest": contracts,
        "TranscriptEvidenceSelectionResult": contracts,
        "TranscriptEvidenceSelector": selector,
    }
    for name, root_export in root_exports.items():
        defined = getattr(defining_modules[name], name)
        assert getattr(canonical, name) is root_export is defined
        assert defined.__module__ == defining_modules[name].__name__
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(
            "projectkoios.ingestion.transcript_evidence_selection"
        )


def test__selector__returns_canonical_page_and_block_order() -> None:
    transcript = _transcript()
    request = _request(
        transcript,
        (
            transcript.blocks[2].record_id,
            transcript.blocks[0].record_id,
        ),
    )

    result = TranscriptEvidenceSelector().select(request=request)

    assert (
        result.outcome is TranscriptEvidenceSelectionOutcome.EVIDENCE_AVAILABLE
    )
    assert tuple(block.block_id for block in result.blocks) == (
        "root-block-a",
        "root-block-c",
    )
    assert tuple(page.page_index for page in result.pages) == (0, 1)
    assert tuple(page.printed_page_label for page in result.pages) == ("i", "2")
    assert tuple(page.page_id for page in result.pages) == (
        transcript.pages[0].page_id,
        transcript.pages[1].page_id,
    )
    assert all(
        type(block) is SelectedTranscriptBlockEvidence
        for block in result.blocks
    )
    assert all(
        type(page) is SelectedTranscriptPageEvidence for page in result.pages
    )


def test__selector__distinguishes_duplicate_and_missing_ids() -> None:
    transcript = _transcript()
    duplicate_id = transcript.blocks[0].record_id

    duplicate = TranscriptEvidenceSelector().select(
        request=_request(transcript, (duplicate_id, duplicate_id))
    )
    missing_id = f"clean-transcript-block:sha256:{'0' * 64}"
    missing = TranscriptEvidenceSelector().select(
        request=_request(transcript, (missing_id,))
    )

    assert duplicate.outcome is (
        TranscriptEvidenceSelectionOutcome.INVALID_SELECTION
    )
    assert duplicate.selection_errors == ("duplicate_block_record_ids",)
    assert duplicate.duplicate_block_record_ids == (duplicate_id,)
    assert duplicate.pages == duplicate.blocks == ()
    assert missing.outcome is TranscriptEvidenceSelectionOutcome.MISSING_BLOCK
    assert missing.missing_block_record_ids == (missing_id,)
    assert missing.pages == missing.blocks == ()


def test__selector__retains_separate_raw_and_clean_text_with_digests() -> None:
    transcript = _transcript()
    source = transcript.blocks[0]

    result = TranscriptEvidenceSelector().action(
        request=_request(transcript, (source.record_id,))
    )
    block = result.blocks[0]

    assert block.indexed_clean_text == source.clean_text
    assert block.retained_raw_text == source.raw_text
    assert block.indexed_clean_text != block.retained_raw_text
    assert (
        block.indexed_clean_text_sha256
        == hashlib.sha256(source.clean_text.encode("utf-8")).hexdigest()
    )
    assert (
        block.retained_raw_text_sha256
        == hashlib.sha256(source.raw_text.encode("utf-8")).hexdigest()
    )
    assert block.mapping_basis is (
        TranscriptEvidenceMappingBasis.CLEAN_TRANSCRIPT_BLOCK_EXACT_PAIR
    )
    assert block.block_id == source.block_id
    assert block.block_record_id == source.record_id


def test__selector__fails_closed_for_global_transcript_warnings() -> None:
    transcript = _transcript(warnings=("layout_reading_order_is_proposed",))

    result = TranscriptEvidenceSelector().select(
        request=_request(transcript, (transcript.blocks[0].record_id,))
    )

    assert result.outcome is (
        TranscriptEvidenceSelectionOutcome.WARNING_INSPECTION_REQUIRED
    )
    assert result.transcript_warnings == ("layout_reading_order_is_proposed",)
    assert result.warnings_requiring_inspection == result.transcript_warnings
    assert not result.block_resolved_warning_inspection_possible
    assert result.pages == result.blocks == ()


def test__selector__fails_closed_for_incomplete_transcript_membership() -> None:
    transcript = _transcript(incomplete_page_membership=True)

    result = TranscriptEvidenceSelector().select(
        request=_request(transcript, (transcript.blocks[0].record_id,))
    )

    assert result.outcome is (
        TranscriptEvidenceSelectionOutcome.TRANSCRIPT_NOT_COMPLETE
    )
    assert result.pages == result.blocks == ()


def test__selector__is_deterministic_and_action_equals_select() -> None:
    transcript = _transcript()
    first_request = _request(
        transcript,
        (transcript.blocks[2].record_id, transcript.blocks[0].record_id),
    )
    second_request = _request(
        transcript,
        (transcript.blocks[0].record_id, transcript.blocks[2].record_id),
    )
    selector = TranscriptEvidenceSelector()

    selected = selector.select(request=first_request)
    acted = selector.action(request=second_request)

    assert first_request == second_request
    assert first_request.request_id == second_request.request_id
    assert selected == acted
    assert selected.result_id == acted.result_id
    assert isinstance(first_request, DataObjectActionRequest)
    assert isinstance(selected, DataObjectActionResult)
    assert isinstance(selector, DataObjectActionizer)
    assert isinstance(selected, TranscriptEvidenceSelectionResult)
    assert selected.request_id == first_request.request_id
    with pytest.raises(FrozenInstanceError):
        replace(first_request).selected_block_record_ids = ()  # type: ignore[misc]
