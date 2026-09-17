from __future__ import annotations

import hashlib
import math
import os
import re
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from pathlib import Path

from projectkoios.ingestion.equations import (
    EquationCandidate,
    EquationCandidateKind,
    EquationDetectionResult,
    EquationEvidenceStatus,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import BoundingBox, ExtractedPage, SourceSpan
from projectkoios.ingestion.pdf.models import (
    PageRegionSelection,
    RenderedRegion,
)
from projectkoios.ingestion.pdf.renderer import PyMuPdfRegionRenderer

EQUATION_ENRICHMENT_CONTRACT_VERSION = "1.0"
_MAX_ASSEMBLIES = 256
_MAX_DIAGNOSTIC_BYTES = 4_000_000
_MAX_OUTPUT_BYTES = 8_000_000
_MAX_LATEX_CHARACTERS = 16_384
_COORDINATE_TUPLE = re.compile(
    r"(?:\d+\s*=\s*\d+\s*[,;]\s*){2,}\d+", re.IGNORECASE
)
_IO_FALSE_POSITIVE = re.compile(r"\bI\s*=\s*O\b", re.IGNORECASE)
_MATH_SIGNAL = re.compile(r"[=≈≃≤≥≠∝∑∫√∂∇∞±→←∏⋅·^_]|\\[A-Za-z]+")


class EquationAssemblyKind(StrEnum):
    DISPLAY = "display"
    INLINE = "inline"


class EquationRecognitionStatus(StrEnum):
    PROPOSED = "proposed"
    FAILED = "failed"
    NOT_REQUESTED = "not_requested"


class EquationIndexTier(StrEnum):
    PRIMARY = "primary"
    AUXILIARY = "auxiliary"
    REJECTED = "rejected"


@dataclass(frozen=True)
class EquationAssembly:
    assembly_id: str
    detection_result_id: str
    candidate_ids: tuple[str, ...]
    detector_evidence_statuses: tuple[EquationEvidenceStatus, ...]
    kind: EquationAssemblyKind
    page_index: int
    printed_page_label: str | None
    source_spans: tuple[SourceSpan, ...]
    source_block_ids: tuple[str, ...]
    raw_fragments: tuple[str, ...]
    sanitized_native_text: str
    control_character_count: int
    source_labels: tuple[str, ...]
    preceding_context_text: str | None
    following_context_text: str | None
    rendered_region: RenderedRegion
    prefilter_reasons: tuple[str, ...]
    rejected: bool
    contract_version: str = EQUATION_ENRICHMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_ENRICHMENT_CONTRACT_VERSION:
            raise ValueError("unsupported equation assembly version")
        if not self.candidate_ids or len(self.candidate_ids) != len(
            set(self.candidate_ids)
        ):
            raise ValueError(
                "assembly candidate IDs must be non-empty and unique"
            )
        if not self.raw_fragments:
            raise ValueError("assembly must retain raw fragments")
        if len(self.detector_evidence_statuses) != len(self.candidate_ids):
            raise ValueError("assembly detector statuses must match candidates")
        if self.page_index < 0:
            raise ValueError("assembly page index must be non-negative")
        if self.control_character_count < 0:
            raise ValueError("control-character count must be non-negative")
        expected = _assembly_id(
            self.detection_result_id,
            self.candidate_ids,
            self.detector_evidence_statuses,
            self.rendered_region.region_id,
            self.sanitized_native_text,
            self.prefilter_reasons,
            self.rejected,
        )
        if self.assembly_id != expected:
            raise ValueError("equation assembly ID is inconsistent")


@dataclass(frozen=True)
class EquationAssemblyArtifact:
    artifact_id: str
    source_id: str
    source_content_hash: str
    document_id: str
    detection_result_id: str
    assemblies: tuple[EquationAssembly, ...]
    contract_version: str = EQUATION_ENRICHMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_ENRICHMENT_CONTRACT_VERSION:
            raise ValueError("unsupported equation assembly artifact version")
        if len(self.assemblies) > _MAX_ASSEMBLIES:
            raise ValueError("equation assembly count exceeds the limit")
        ids = tuple(item.assembly_id for item in self.assemblies)
        if len(ids) != len(set(ids)):
            raise ValueError("equation assembly IDs must be unique")
        expected = stable_id(
            "equation-assembly-artifact",
            EQUATION_ENRICHMENT_CONTRACT_VERSION,
            self.source_id,
            self.source_content_hash,
            self.document_id,
            self.detection_result_id,
            ids,
        )
        if self.artifact_id != expected:
            raise ValueError("equation assembly artifact ID is inconsistent")


@dataclass(frozen=True)
class EquationRecognitionResource:
    name: str
    path: str
    sha256: str
    byte_size: int

    def __post_init__(self) -> None:
        if not self.name or not self.path:
            raise ValueError("recognition resource identity must be complete")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("recognition resource hash must be SHA-256")
        if self.byte_size <= 0:
            raise ValueError("recognition resource size must be positive")


@dataclass(frozen=True)
class EquationRecognitionProcessorIdentity:
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    executable_sha256: str
    executable_semantic_sha256: str
    resources: tuple[EquationRecognitionResource, ...]
    temperature: float

    @property
    def identity_digest(self) -> str:
        return stable_id(
            "equation-recognition-processor",
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
            self.executable_semantic_sha256,
            self.resources,
            self.temperature,
        )

    def __post_init__(self) -> None:
        if not all(
            (
                self.processor_name,
                self.processor_version,
                self.backend_name,
                self.backend_version,
            )
        ):
            raise ValueError("recognition processor identity must be complete")
        if not re.fullmatch(r"[0-9a-f]{64}", self.executable_sha256):
            raise ValueError("recognition executable hash must be SHA-256")
        if not re.fullmatch(r"[0-9a-f]{64}", self.executable_semantic_sha256):
            raise ValueError(
                "recognition executable semantic hash must be SHA-256"
            )
        names = tuple(item.name for item in self.resources)
        if (
            not names
            or names != tuple(sorted(names))
            or len(names) != len(set(names))
        ):
            raise ValueError(
                "recognition resources must be non-empty, unique, and sorted"
            )
        if (
            not math.isfinite(self.temperature)
            or not 0.0 < self.temperature <= 1.0
        ):
            raise ValueError("recognition temperature must be in (0, 1]")


@dataclass(frozen=True)
class EquationRecognitionProposal:
    proposal_id: str
    assembly_id: str
    status: EquationRecognitionStatus
    latex: str | None
    mathml: str | None
    warning_codes: tuple[str, ...]
    failure_message: str | None
    processor_identity_digest: str
    contract_version: str = EQUATION_ENRICHMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_ENRICHMENT_CONTRACT_VERSION:
            raise ValueError(
                "unsupported equation recognition proposal version"
            )
        if self.status is EquationRecognitionStatus.PROPOSED and not self.latex:
            raise ValueError("proposed equation recognition requires LaTeX")
        if (
            self.status is not EquationRecognitionStatus.PROPOSED
            and self.latex is not None
        ):
            raise ValueError(
                "non-proposed equation recognition cannot contain LaTeX"
            )
        if self.latex is not None and len(self.latex) > _MAX_LATEX_CHARACTERS:
            raise ValueError("recognized LaTeX exceeds the limit")
        expected = stable_id(
            "equation-recognition-proposal",
            EQUATION_ENRICHMENT_CONTRACT_VERSION,
            self.assembly_id,
            self.status,
            self.latex,
            self.mathml,
            self.warning_codes,
            self.failure_message,
            self.processor_identity_digest,
        )
        if self.proposal_id != expected:
            raise ValueError("equation recognition proposal ID is inconsistent")


@dataclass(frozen=True)
class EquationRecognitionArtifact:
    artifact_id: str
    assembly_artifact_id: str
    processor_identity: EquationRecognitionProcessorIdentity
    proposals: tuple[EquationRecognitionProposal, ...]
    invocation_exit_code: int
    diagnostic_byte_size: int
    diagnostic_sha256: str
    contract_version: str = EQUATION_ENRICHMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_ENRICHMENT_CONTRACT_VERSION:
            raise ValueError(
                "unsupported equation recognition artifact version"
            )
        if (
            self.diagnostic_byte_size < 0
            or self.diagnostic_byte_size > _MAX_DIAGNOSTIC_BYTES
        ):
            raise ValueError("recognition diagnostic size is out of bounds")
        if not re.fullmatch(r"[0-9a-f]{64}", self.diagnostic_sha256):
            raise ValueError("recognition diagnostic hash must be SHA-256")
        proposal_ids = tuple(item.proposal_id for item in self.proposals)
        expected = stable_id(
            "equation-recognition-artifact",
            EQUATION_ENRICHMENT_CONTRACT_VERSION,
            self.assembly_artifact_id,
            self.processor_identity.identity_digest,
            proposal_ids,
            self.invocation_exit_code,
            self.diagnostic_byte_size,
            self.diagnostic_sha256,
        )
        if self.artifact_id != expected:
            raise ValueError("equation recognition artifact ID is inconsistent")


@dataclass(frozen=True)
class EquationIndexRecord:
    record_id: str
    assembly_id: str
    candidate_ids: tuple[str, ...]
    tier: EquationIndexTier
    completeness: float
    reasons: tuple[str, ...]
    page_index: int
    printed_page_label: str | None
    source_block_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    source_bounding_box: BoundingBox
    rendered_region_id: str
    rendered_region_sha256: str
    raw_fragments: tuple[str, ...]
    sanitized_native_text: str
    latex_proposal: str | None
    mathml_proposal: str | None
    preceding_context_text: str | None
    following_context_text: str | None
    retrieval_text: str
    contract_version: str = EQUATION_ENRICHMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_ENRICHMENT_CONTRACT_VERSION:
            raise ValueError("unsupported equation index record version")
        if not 0.0 <= self.completeness <= 1.0:
            raise ValueError("equation completeness must be in [0, 1]")
        expected = stable_id(
            "equation-index-record",
            EQUATION_ENRICHMENT_CONTRACT_VERSION,
            self.assembly_id,
            self.tier,
            self.completeness,
            self.reasons,
            self.retrieval_text,
        )
        if self.record_id != expected:
            raise ValueError("equation index record ID is inconsistent")


@dataclass(frozen=True)
class EquationIndexArtifact:
    artifact_id: str
    source_id: str
    source_content_hash: str
    assembly_artifact_id: str
    recognition_artifact_id: str
    records: tuple[EquationIndexRecord, ...]
    contract_version: str = EQUATION_ENRICHMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_ENRICHMENT_CONTRACT_VERSION:
            raise ValueError("unsupported equation index artifact version")
        ids = tuple(item.record_id for item in self.records)
        if len(ids) != len(set(ids)):
            raise ValueError("equation index record IDs must be unique")
        expected = stable_id(
            "equation-index-artifact",
            EQUATION_ENRICHMENT_CONTRACT_VERSION,
            self.source_id,
            self.source_content_hash,
            self.assembly_artifact_id,
            self.recognition_artifact_id,
            ids,
        )
        if self.artifact_id != expected:
            raise ValueError("equation index artifact ID is inconsistent")


class DeterministicEquationAssembler:
    """Group same-line display fragments and preserve all evidence layers."""

    def __init__(
        self, *, renderer: PyMuPdfRegionRenderer | None = None
    ) -> None:
        self.renderer = renderer or PyMuPdfRegionRenderer()

    def assemble(
        self,
        detection: EquationDetectionResult,
        content: bytes,
    ) -> EquationAssemblyArtifact:
        document = detection.detection_input.document
        if hashlib.sha256(content).hexdigest() != document.source.content_hash:
            raise ValueError("equation assembly requires exact PDF bytes")
        block_text = {
            block.block_id: block.text
            for page in document.pages
            for block in page.blocks
            if block.text is not None
        }
        groups = _candidate_groups(detection)
        selections = tuple(
            PageRegionSelection.for_bounding_box(
                document.source,
                group[0].rendered_region.page_index,
                _assembly_box(
                    group,
                    document.pages[group[0].rendered_region.page_index],
                ),
            )
            for group in groups
        )
        rendered = (
            self.renderer.render(
                document.source,
                BytesIO(content),
                selections,
            )
            if selections
            else ()
        )
        assemblies = tuple(
            _assembly_from_group(detection, group, region, block_text)
            for group, region in zip(groups, rendered, strict=True)
        )
        artifact_id = stable_id(
            "equation-assembly-artifact",
            EQUATION_ENRICHMENT_CONTRACT_VERSION,
            document.source.source_id,
            document.source.content_hash,
            document.document_id,
            detection.result_id,
            tuple(item.assembly_id for item in assemblies),
        )
        return EquationAssemblyArtifact(
            artifact_id=artifact_id,
            source_id=document.source.source_id,
            source_content_hash=document.source.content_hash,
            document_id=document.document_id,
            detection_result_id=detection.result_id,
            assemblies=assemblies,
        )


class Pix2TexCliEquationRecognizer:
    """Bounded external pix2tex adapter with explicit model identities."""

    def __init__(
        self,
        executable: Path,
        *,
        backend_version: str,
        resources: tuple[tuple[str, Path], ...],
        temperature: float = 0.01,
        timeout_seconds: int = 900,
    ) -> None:
        self.executable = executable.expanduser().resolve()
        if not self.executable.is_file() or not os.access(
            self.executable, os.X_OK
        ):
            raise ValueError("pix2tex executable is not executable")
        if timeout_seconds <= 0 or timeout_seconds > 3600:
            raise ValueError("pix2tex timeout must be in (0, 3600]")
        self.timeout_seconds = timeout_seconds
        resource_values = tuple(
            EquationRecognitionResource(
                name=name,
                path=str(path.expanduser().resolve()),
                sha256=hashlib.sha256(
                    path.expanduser().resolve().read_bytes()
                ).hexdigest(),
                byte_size=path.expanduser().resolve().stat().st_size,
            )
            for name, path in sorted(resources)
        )
        executable_content = self.executable.read_bytes()
        self.identity = EquationRecognitionProcessorIdentity(
            processor_name="pix2tex-cli-equation-recognizer",
            processor_version="1",
            backend_name="pix2tex",
            backend_version=backend_version,
            executable_sha256=hashlib.sha256(executable_content).hexdigest(),
            executable_semantic_sha256=_executable_semantic_sha256(
                executable_content
            ),
            resources=resource_values,
            temperature=temperature,
        )

    def process(
        self,
        artifact: EquationAssemblyArtifact,
    ) -> EquationRecognitionArtifact:
        if self.executable.is_symlink() or not self.executable.is_file():
            raise ValueError("pix2tex executable path became unsafe")
        if (
            hashlib.sha256(self.executable.read_bytes()).hexdigest()
            != self.identity.executable_sha256
        ):
            raise ValueError("pix2tex executable changed after planning")
        for resource in self.identity.resources:
            path = Path(resource.path)
            if path.is_symlink() or not path.is_file():
                raise ValueError(
                    f"pix2tex resource path became unsafe: {resource.name}"
                )
            content = path.read_bytes()
            if (
                len(content) != resource.byte_size
                or hashlib.sha256(content).hexdigest() != resource.sha256
            ):
                raise ValueError(
                    f"pix2tex resource changed after planning: {resource.name}"
                )
        selected = tuple(
            assembly
            for assembly in artifact.assemblies
            if assembly.kind is EquationAssemblyKind.DISPLAY
            and not assembly.rejected
        )
        latex_by_id: dict[str, str] = {}
        exit_code = 0
        diagnostic = b""
        if selected:
            exit_code, diagnostic, latex_by_id = self._invoke(selected)
        proposals = tuple(
            _recognition_proposal(
                assembly,
                latex=latex_by_id.get(assembly.assembly_id),
                exit_code=exit_code,
                processor_identity_digest=self.identity.identity_digest,
            )
            for assembly in artifact.assemblies
        )
        diagnostic_sha256 = hashlib.sha256(diagnostic).hexdigest()
        artifact_id = stable_id(
            "equation-recognition-artifact",
            EQUATION_ENRICHMENT_CONTRACT_VERSION,
            artifact.artifact_id,
            self.identity.identity_digest,
            tuple(item.proposal_id for item in proposals),
            exit_code,
            len(diagnostic),
            diagnostic_sha256,
        )
        return EquationRecognitionArtifact(
            artifact_id=artifact_id,
            assembly_artifact_id=artifact.artifact_id,
            processor_identity=self.identity,
            proposals=proposals,
            invocation_exit_code=exit_code,
            diagnostic_byte_size=len(diagnostic),
            diagnostic_sha256=diagnostic_sha256,
        )

    def _invoke(
        self,
        assemblies: tuple[EquationAssembly, ...],
    ) -> tuple[int, bytes, dict[str, str]]:
        with tempfile.TemporaryDirectory(prefix="koios-pix2tex-") as directory:
            root = Path(directory)
            paths: dict[Path, str] = {}
            for index, assembly in enumerate(assemblies):
                suffix = assembly.assembly_id.rsplit(":", 1)[-1]
                path = root / f"{index:04d}-{suffix}.png"
                path.write_bytes(assembly.rendered_region.content)
                paths[path.resolve()] = assembly.assembly_id
            stdout_path = root / "stdout.txt"
            stderr_path = root / "stderr.txt"
            environment = dict(os.environ)
            environment["NO_ALBUMENTATIONS_UPDATE"] = "1"
            command = [
                str(self.executable),
                "--no-cuda",
                "--temperature",
                str(self.identity.temperature),
                *(str(path) for path in paths),
            ]
            with (
                stdout_path.open("wb") as stdout,
                stderr_path.open("wb") as stderr,
            ):
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    env=environment,
                )
                try:
                    exit_code = process.wait(timeout=self.timeout_seconds)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    exit_code = 124
            if stdout_path.stat().st_size > _MAX_OUTPUT_BYTES:
                raise ValueError("pix2tex output exceeds the limit")
            if stderr_path.stat().st_size > _MAX_DIAGNOSTIC_BYTES:
                raise ValueError("pix2tex diagnostics exceed the limit")
            output = stdout_path.read_text(encoding="utf-8", errors="strict")
            diagnostic = stderr_path.read_bytes()
            results: dict[str, str] = {}
            for line in output.splitlines():
                name, separator, latex = line.partition(": ")
                if not separator:
                    continue
                path = Path(name).resolve()
                assembly_id = paths.get(path)
                if assembly_id is None or assembly_id in results:
                    raise ValueError(
                        "pix2tex returned an unexpected image path"
                    )
                text = latex.strip()
                if text:
                    results[assembly_id] = text
            return exit_code, diagnostic, results


def build_equation_index(
    assembly: EquationAssemblyArtifact,
    recognition: EquationRecognitionArtifact,
) -> EquationIndexArtifact:
    if recognition.assembly_artifact_id != assembly.artifact_id:
        raise ValueError("recognition does not match equation assembly")
    proposals = {item.assembly_id: item for item in recognition.proposals}
    records = tuple(
        _index_record(item, proposals[item.assembly_id])
        for item in assembly.assemblies
    )
    artifact_id = stable_id(
        "equation-index-artifact",
        EQUATION_ENRICHMENT_CONTRACT_VERSION,
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


def _candidate_groups(
    detection: EquationDetectionResult,
) -> tuple[tuple[EquationCandidate, ...], ...]:
    by_page: dict[int, list[EquationCandidate]] = {}
    for candidate in detection.candidates:
        by_page.setdefault(candidate.rendered_region.page_index, []).append(
            candidate
        )
    groups: list[tuple[EquationCandidate, ...]] = []
    for page_index in sorted(by_page):
        values = by_page[page_index]
        displays = sorted(
            (
                item
                for item in values
                if item.kind is EquationCandidateKind.DISPLAY
            ),
            key=lambda item: (
                item.rendered_region.source_bounding_box[1],
                item.rendered_region.source_bounding_box[0],
                item.candidate_id,
            ),
        )
        page_width = detection.detection_input.document.pages[page_index].width
        remaining = list(displays)
        while remaining:
            group = [remaining.pop(0)]
            changed = True
            while changed:
                changed = False
                group_box = _union_boxes(
                    tuple(
                        item.rendered_region.source_bounding_box
                        for item in group
                    )
                )
                for candidate in tuple(remaining):
                    box = candidate.rendered_region.source_bounding_box
                    if _same_equation_line(group_box, box, page_width):
                        group.append(candidate)
                        remaining.remove(candidate)
                        changed = True
            groups.append(
                tuple(
                    sorted(
                        group,
                        key=lambda item: (
                            item.rendered_region.source_bounding_box[0]
                        ),
                    )
                )
            )
        groups.extend(
            (candidate,)
            for candidate in sorted(
                (
                    item
                    for item in values
                    if item.kind is EquationCandidateKind.INLINE
                ),
                key=lambda item: (
                    item.rendered_region.source_bounding_box[1],
                    item.rendered_region.source_bounding_box[0],
                    item.candidate_id,
                ),
            )
        )
    return tuple(groups)


def _same_equation_line(
    first: BoundingBox, second: BoundingBox, page_width: float
) -> bool:
    midpoint = page_width / 2.0
    if (first[2] <= midpoint and second[0] >= midpoint) or (
        second[2] <= midpoint and first[0] >= midpoint
    ):
        return False
    overlap = min(first[3], second[3]) - max(first[1], second[1])
    minimum_height = min(first[3] - first[1], second[3] - second[1])
    if overlap <= 0.2 * minimum_height:
        return False
    horizontal_gap = max(first[0], second[0]) - min(first[2], second[2])
    return horizontal_gap <= max(48.0, page_width * 0.14)


def _assembly_box(
    group: tuple[EquationCandidate, ...], page: ExtractedPage
) -> BoundingBox:
    boxes = list(item.rendered_region.source_bounding_box for item in group)
    union = _union_boxes(tuple(boxes))
    changed = True
    while changed:
        changed = False
        for block in page.blocks:
            if block.text is None or not _looks_like_math_fragment(block.text):
                continue
            block_box = _block_box(block.source_spans)
            if block_box is None or block_box in boxes:
                continue
            if not _same_equation_line(union, block_box, page.width):
                continue
            boxes.append(block_box)
            union = _union_boxes(tuple(boxes))
            changed = True
    return (
        max(0.0, union[0] - 3.0),
        max(0.0, union[1] - 3.0),
        min(page.width, union[2] + 3.0),
        min(page.height, union[3] + 3.0),
    )


def _block_box(spans: tuple[SourceSpan, ...]) -> BoundingBox | None:
    boxes = tuple(
        span.bounding_box for span in spans if span.bounding_box is not None
    )
    return _union_boxes(boxes) if boxes else None


def _looks_like_math_fragment(text: str) -> bool:
    normalized = " ".join(text.split())
    if not normalized or len(normalized) > 512:
        return False
    if len(normalized.split()) > 12:
        return False
    return len(normalized) <= 24 or bool(_MATH_SIGNAL.search(normalized))


def _assembly_from_group(
    detection: EquationDetectionResult,
    group: tuple[EquationCandidate, ...],
    region: RenderedRegion,
    block_text: dict[str, str],
) -> EquationAssembly:
    candidate_ids = tuple(item.candidate_id for item in group)
    raw_fragments = tuple(item.raw_text for item in group)
    joined = " ".join(
        fragment.strip() for fragment in raw_fragments if fragment.strip()
    )
    sanitized, control_count = _sanitize_native_text(joined)
    labels = tuple(
        item.source_label for item in group if item.source_label is not None
    )
    source_spans = tuple(span for item in group for span in item.source_spans)
    block_ids = tuple(dict.fromkeys(item.source_block_id for item in group))
    first = group[0]
    last = group[-1]
    preceding_id = (
        first.preceding_context.block_id if first.preceding_context else None
    )
    following_id = (
        last.following_context.block_id if last.following_context else None
    )
    reasons: list[str] = []
    rejected = False
    if control_count:
        reasons.append("control_characters_sanitized")
    if _IO_FALSE_POSITIVE.search(sanitized):
        reasons.append("io_typographic_false_positive")
        rejected = True
    if _COORDINATE_TUPLE.search(sanitized) or (
        "to M" in sanitized and sanitized.count("=2") >= 2
    ):
        reasons.append("coordinate_tuple_false_positive")
        rejected = True
    kind = (
        EquationAssemblyKind.DISPLAY
        if any(item.kind is EquationCandidateKind.DISPLAY for item in group)
        else EquationAssemblyKind.INLINE
    )
    if kind is EquationAssemblyKind.INLINE:
        reasons.append("inline_context_only")
        if len(sanitized) > 80 or len(sanitized.split()) > 12:
            reasons.append("prose_relation")
    detector_statuses = tuple(item.evidence_status for item in group)
    assembly_id = _assembly_id(
        detection.result_id,
        candidate_ids,
        detector_statuses,
        region.region_id,
        sanitized,
        tuple(reasons),
        rejected,
    )
    return EquationAssembly(
        assembly_id=assembly_id,
        detection_result_id=detection.result_id,
        candidate_ids=candidate_ids,
        detector_evidence_statuses=detector_statuses,
        kind=kind,
        page_index=region.page_index,
        printed_page_label=region.printed_page_label,
        source_spans=source_spans,
        source_block_ids=block_ids,
        raw_fragments=raw_fragments,
        sanitized_native_text=sanitized,
        control_character_count=control_count,
        source_labels=labels,
        preceding_context_text=block_text.get(preceding_id)
        if preceding_id
        else None,
        following_context_text=block_text.get(following_id)
        if following_id
        else None,
        rendered_region=region,
        prefilter_reasons=tuple(reasons),
        rejected=rejected,
    )


def _recognition_proposal(
    assembly: EquationAssembly,
    *,
    latex: str | None,
    exit_code: int,
    processor_identity_digest: str,
) -> EquationRecognitionProposal:
    warnings: list[str] = []
    failure: str | None = None
    mathml: str | None = None
    if assembly.rejected or assembly.kind is EquationAssemblyKind.INLINE:
        status = EquationRecognitionStatus.NOT_REQUESTED
        warnings.append("recognition_not_requested_for_non_primary_shape")
    elif exit_code != 0 or latex is None:
        status = EquationRecognitionStatus.FAILED
        warnings.append("pix2tex_failed")
        failure = (
            f"pix2tex exit code {exit_code}; no bounded proposal was retained"
        )
    else:
        status = EquationRecognitionStatus.PROPOSED
        warnings.append("recognition_confidence_unavailable")
        if not _latex_is_well_formed(latex):
            warnings.append("latex_structure_suspect")
        try:
            from latex2mathml.converter import convert

            mathml = convert(latex)
        except Exception:  # latex2mathml exposes multiple parser exceptions
            warnings.append("mathml_conversion_unavailable")
    proposal_id = stable_id(
        "equation-recognition-proposal",
        EQUATION_ENRICHMENT_CONTRACT_VERSION,
        assembly.assembly_id,
        status,
        latex,
        mathml,
        tuple(warnings),
        failure,
        processor_identity_digest,
    )
    return EquationRecognitionProposal(
        proposal_id=proposal_id,
        assembly_id=assembly.assembly_id,
        status=status,
        latex=latex,
        mathml=mathml,
        warning_codes=tuple(warnings),
        failure_message=failure,
        processor_identity_digest=processor_identity_digest,
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
        EQUATION_ENRICHMENT_CONTRACT_VERSION,
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


def _executable_semantic_sha256(content: bytes) -> str:
    if content.startswith(b"#!"):
        _, separator, remainder = content.partition(b"\n")
        content = b"#!python\n" + remainder if separator else b"#!python"
    return hashlib.sha256(content).hexdigest()


def _sanitize_native_text(value: str) -> tuple[str, int]:
    output: list[str] = []
    count = 0
    for character in value:
        if unicodedata.category(character) == "Cc":
            count += 1
            output.append(" " if character in "\n\r\t" else "�")
        else:
            output.append(character)
    return " ".join("".join(output).split()), count


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


def _assembly_id(
    detection_result_id: str,
    candidate_ids: tuple[str, ...],
    detector_statuses: tuple[EquationEvidenceStatus, ...],
    rendered_region_id: str,
    sanitized_native_text: str,
    reasons: tuple[str, ...],
    rejected: bool,
) -> str:
    return stable_id(
        "equation-assembly",
        EQUATION_ENRICHMENT_CONTRACT_VERSION,
        detection_result_id,
        candidate_ids,
        detector_statuses,
        rendered_region_id,
        sanitized_native_text,
        reasons,
        rejected,
    )


def _union_boxes(boxes: tuple[BoundingBox, ...]) -> BoundingBox:
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )
