"""Deterministic equation-index construction."""

from __future__ import annotations

import re

from projectkoios.ingestion.equations.assembly.kind import EquationAssemblyKind
from projectkoios.ingestion.equations.assembly.model import EquationAssembly
from projectkoios.ingestion.equations.assembly.result import (
    EquationAssemblyResult,
)
from projectkoios.ingestion.equations.detection import EquationEvidenceStatus
from projectkoios.ingestion.equations.index.artifact import (
    EquationIndexArtifact,
)
from projectkoios.ingestion.equations.index.identity import (
    EQUATION_INDEX_CONTRACT_VERSION,
)
from projectkoios.ingestion.equations.index.record import EquationIndexRecord
from projectkoios.ingestion.equations.index.tier import EquationIndexTier
from projectkoios.ingestion.equations.recognition.artifact import (
    EquationRecognitionArtifact,
)
from projectkoios.ingestion.equations.recognition.proposal import (
    EquationRecognitionProposal,
)
from projectkoios.ingestion.equations.recognition.status import (
    EquationRecognitionStatus,
)
from projectkoios.ingestion.identity import stable_id

_MAX_LATEX_CHARACTERS = 16_384
_MATH_SIGNAL = re.compile(r"[=≈≃≤≥≠∝∑∫√∂∇∞±→←∏⋅·^_]|\\[A-Za-z]+")


def build_equation_index(
    assembly: EquationAssemblyResult,
    recognition: EquationRecognitionArtifact,
) -> EquationIndexArtifact:
    """Build compact index records from correlated exact evidence."""

    if recognition.assembly_artifact_id != assembly.artifact_id:
        raise ValueError("recognition does not match equation assembly")
    proposals = {item.assembly_id: item for item in recognition.proposals}
    records = tuple(
        _index_record(item, proposals[item.assembly_id])
        for item in assembly.assemblies
    )
    artifact_id = stable_id(
        "equation-index-artifact",
        EQUATION_INDEX_CONTRACT_VERSION,
        assembly.source_id,
        assembly.source_content_hash,
        assembly.artifact_id,
        recognition.artifact_id,
        tuple(record.record_id for record in records),
    )
    return EquationIndexArtifact(
        artifact_id=artifact_id,
        source_id=assembly.source_id,
        source_content_hash=assembly.source_content_hash,
        assembly_artifact_id=assembly.artifact_id,
        recognition_artifact_id=recognition.artifact_id,
        records=records,
    )


def _index_record(
    assembly: EquationAssembly,
    recognition: EquationRecognitionProposal,
) -> EquationIndexRecord:
    reasons = list(assembly.prefilter_reasons)
    score = 0.0
    if assembly.kind is EquationAssemblyKind.DISPLAY:
        score += 0.35
    if len(assembly.sanitized_native_text.replace(" ", "")) >= 7:
        score += 0.05
    if _MATH_SIGNAL.search(assembly.sanitized_native_text):
        score += 0.1
    if assembly.source_labels:
        score += 0.1
    if assembly.control_character_count == 0:
        score += 0.05
    detector_is_proposed = all(
        status is EquationEvidenceStatus.PROPOSED
        for status in assembly.detector_evidence_statuses
    )
    if detector_is_proposed:
        score += 0.1
    else:
        reasons.append("detector_ambiguity_retained_as_auxiliary")
    indexable_proposal, proposal_reasons = _proposal_is_indexable(
        assembly, recognition
    )
    reasons.extend(proposal_reasons)
    if recognition.latex:
        score += 0.2
        if indexable_proposal:
            score += 0.15
    if recognition.status is not EquationRecognitionStatus.PROPOSED:
        reasons.append("recognition_not_proposed")
    score = round(min(1.0, max(0.0, score)), 6)
    if assembly.rejected:
        tier = EquationIndexTier.REJECTED
    elif assembly.kind is EquationAssemblyKind.INLINE:
        tier = EquationIndexTier.AUXILIARY
    elif detector_is_proposed and score >= 0.75 and indexable_proposal:
        tier = EquationIndexTier.PRIMARY
    else:
        tier = EquationIndexTier.AUXILIARY
        reasons.append("insufficient_completeness_for_primary_index")
    retrieval_text = _index_text(assembly, recognition, tier)
    record_id = stable_id(
        "equation-index-record",
        EQUATION_INDEX_CONTRACT_VERSION,
        assembly.assembly_id,
        tier,
        score,
        tuple(dict.fromkeys(reasons)),
        retrieval_text,
    )
    return EquationIndexRecord(
        record_id=record_id,
        assembly_id=assembly.assembly_id,
        candidate_ids=assembly.candidate_ids,
        tier=tier,
        completeness=score,
        reasons=tuple(dict.fromkeys(reasons)),
        page_index=assembly.page_index,
        printed_page_label=assembly.printed_page_label,
        source_block_ids=assembly.source_block_ids,
        source_spans=assembly.source_spans,
        source_bounding_box=assembly.rendered_region.source_bounding_box,
        rendered_region_id=assembly.rendered_region.region_id,
        rendered_region_sha256=assembly.rendered_region.content_sha256,
        raw_fragments=assembly.raw_fragments,
        sanitized_native_text=assembly.sanitized_native_text,
        latex_proposal=recognition.latex,
        mathml_proposal=recognition.mathml,
        preceding_context_text=assembly.preceding_context_text,
        following_context_text=assembly.following_context_text,
        retrieval_text=retrieval_text,
    )


def _index_text(
    assembly: EquationAssembly,
    recognition: EquationRecognitionProposal,
    tier: EquationIndexTier,
) -> str:
    parts = [f"Equation retrieval tier: {tier.value}"]
    if assembly.preceding_context_text:
        parts.append(
            f"Preceding context:\n{assembly.preceding_context_text.strip()}"
        )
    parts.append(
        f"Sanitized native PDF equation text:\n{assembly.sanitized_native_text}"
    )
    if recognition.latex:
        parts.append(f"Unaccepted LaTeX proposal:\n{recognition.latex}")
    if assembly.following_context_text:
        parts.append(
            f"Following context:\n{assembly.following_context_text.strip()}"
        )
    return "\n\n".join(parts)


def _proposal_is_indexable(
    assembly: EquationAssembly,
    recognition: EquationRecognitionProposal,
) -> tuple[bool, tuple[str, ...]]:
    latex = recognition.latex
    reasons: list[str] = []
    if latex is None:
        return False, ()
    if not _latex_is_well_formed(latex):
        reasons.append("latex_structure_suspect")
    if len(latex) > 2_048:
        reasons.append("latex_output_excessive")
    if recognition.mathml is None:
        reasons.append("mathml_proposal_unavailable")
    native = assembly.sanitized_native_text
    if len("".join(native.split())) < 7:
        reasons.append("native_evidence_too_short")
    if native.casefold().startswith(("where ", "for ", "with ", "and ")):
        reasons.append("native_prose_prefix")
    if re.search(
        r"\\mathrm\{[^}]*[A-Za-z]{4,}(?:~|\\ )[A-Za-z]{3,}",
        latex,
    ):
        reasons.append("latex_prose_suspect")
    prose_words = {
        word.casefold()
        for word in re.findall(r"\\mathrm\{[^}]*?([A-Za-z]{4,})", latex)
    }
    if prose_words - {"cell", "shift", "spin", "reference"}:
        reasons.append("latex_prose_suspect")
    for source_symbol, latex_symbol in (
        ("=", "="),
        ("∫", r"\int"),
        ("∑", r"\sum"),
        ("√", r"\sqrt"),
        ("∂", r"\partial"),
    ):
        if source_symbol in native and latex_symbol not in latex:
            reasons.append("latex_native_signal_mismatch")
            break
    if any(
        latex.count(token) > limit
        for token, limit in (
            (r"\qquad", 20),
            (r"\mathrm{~}", 12),
            (r"\ldots", 12),
        )
    ):
        reasons.append("latex_repetition_suspect")
    return not reasons, tuple(reasons)


def _latex_is_well_formed(value: str) -> bool:
    if not value or len(value) > _MAX_LATEX_CHARACTERS:
        return False
    depth = 0
    for character in value:
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth < 0:
                return False
    if depth != 0:
        return False
    return value.count(r"\begin{") == value.count(r"\end{")
