"""Owner validation and typed loading for reading-scale page projections."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import unicodedata
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import cast

from projectkoios.ingestion.identity import stable_id

__all__ = (
    "PAGE_PROJECTION_CONTRACT_VERSION",
    "OwnerValidatedPageProjection",
    "PageProjectionPage",
    "PageProjectionPlanEntry",
    "PageProjectionTextBlock",
    "PageProjectionValidationError",
    "PageProjectionValidationReport",
    "iter_page_projection_pages",
    "iter_page_projection_windows",
    "load_owner_validated_page_projection",
    "load_page_projection_validation_report",
    "page_projection_validation_report_bytes",
    "validate_page_projection",
)

PAGE_PROJECTION_CONTRACT_VERSION = "1.0"
_MAXIMUM_ARTIFACT_BYTES = 1_000_000_000
_MAXIMUM_PAGE_LINE_BYTES = 16_000_000
_MAXIMUM_PAGES = 10_000
_MAXIMUM_BLOCKS_PER_PAGE = 100_000
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_VALIDATION_RULES = (
    "source_digest",
    "private_no_follow_owner_artifacts",
    "physical_and_printed_page_order",
    "citation_alignment",
    "contiguous_block_order",
    "relative_unique_png_paths",
    "caption_exact_normalized_uniqueness_and_paragraph_exclusion_v2",
    "unreviewed_equation_chunk_text_exclusion",
    "summary_count_agreement",
    "paragraph_coverage",
)


class PageProjectionValidationError(ValueError):
    """Raised when page-projection evidence is unsafe or inconsistent."""


@dataclass(frozen=True)
class PageProjectionPlanEntry:
    """Path-free document identity supplied explicitly by an admission plan."""

    document_id: str
    filename: str
    title: str
    source_sha256: str
    expected_page_count: int

    def __post_init__(self) -> None:
        if not self.document_id or len(self.document_id) > 512:
            raise ValueError("page projection document ID is invalid")
        if (
            not self.filename
            or self.filename != Path(self.filename).name
            or "/" in self.filename
            or "\\" in self.filename
        ):
            raise ValueError("page projection filename must be a basename")
        if not self.title or len(self.title) > 16_384:
            raise ValueError("page projection title is invalid")
        if _SHA256.fullmatch(self.source_sha256) is None:
            raise ValueError("page projection source hash must be SHA-256")
        if not 1 <= self.expected_page_count <= _MAXIMUM_PAGES:
            raise ValueError("page projection page count is outside its bounds")


@dataclass(frozen=True)
class PageProjectionTextBlock:
    """One index-eligible paragraph, heading, or validated figure caption."""

    order: int
    text: str
    style: str | None

    def __post_init__(self) -> None:
        if self.order < 0 or not self.text.strip():
            raise ValueError("page projection text block is invalid")
        if self.style not in (None, "heading", "caption"):
            raise ValueError("page projection text style is unsupported")


@dataclass(frozen=True)
class PageProjectionPage:
    """A citation-aligned page containing owner-approved index text."""

    physical_page: int
    printed_page: str | None
    citation_physical_page: int
    citation_printed_page: str | None
    text_blocks: tuple[PageProjectionTextBlock, ...]

    def __post_init__(self) -> None:
        if self.physical_page <= 0:
            raise ValueError("physical page must be positive")
        if self.citation_physical_page != self.physical_page:
            raise ValueError("physical-page citation is inconsistent")
        if self.citation_printed_page != self.printed_page:
            raise ValueError("printed-page citation is inconsistent")
        orders = tuple(block.order for block in self.text_blocks)
        if len(orders) != len(set(orders)) or tuple(sorted(orders)) != orders:
            raise ValueError("text block order must be unique and increasing")

    @property
    def has_paragraph_text(self) -> bool:
        return any(block.style != "caption" for block in self.text_blocks)


@dataclass(frozen=True)
class PageProjectionValidationReport:
    """Path-free identity and reconciliation report for one projection."""

    validation_id: str
    document_id: str
    filename: str
    title: str
    source_sha256: str
    transcript_sha256: str
    summary_sha256: str
    media_manifest_sha256: str
    page_projection_sha256: str
    page_count: int
    paragraph_count: int
    heading_count: int
    figure_count: int
    equation_evidence_count: int
    media_count: int
    paragraph_page_count: int
    paragraph_character_count: int
    baseline_character_count: int
    eligible_baseline_page_count: int
    covered_baseline_page_count: int
    paragraph_character_ratio: float
    paragraph_page_coverage: float
    validation_rules: tuple[str, ...] = _VALIDATION_RULES
    contract_version: str = PAGE_PROJECTION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != PAGE_PROJECTION_CONTRACT_VERSION:
            raise ValueError("unsupported page projection contract version")
        plan = PageProjectionPlanEntry(
            document_id=self.document_id,
            filename=self.filename,
            title=self.title,
            source_sha256=self.source_sha256,
            expected_page_count=self.page_count,
        )
        del plan
        for value in (
            self.transcript_sha256,
            self.summary_sha256,
            self.media_manifest_sha256,
            self.page_projection_sha256,
        ):
            if _SHA256.fullmatch(value) is None:
                raise ValueError("page projection report hash is invalid")
        counts = (
            self.paragraph_count,
            self.heading_count,
            self.figure_count,
            self.equation_evidence_count,
            self.media_count,
            self.paragraph_page_count,
            self.paragraph_character_count,
            self.baseline_character_count,
            self.eligible_baseline_page_count,
            self.covered_baseline_page_count,
        )
        if any(value < 0 for value in counts):
            raise ValueError("page projection report count is negative")
        if self.heading_count > self.paragraph_count:
            raise ValueError("heading count exceeds paragraph count")
        if self.paragraph_page_count > self.page_count:
            raise ValueError("paragraph page count exceeds page count")
        if self.covered_baseline_page_count > self.eligible_baseline_page_count:
            raise ValueError("covered baseline count exceeds eligible count")
        if not 0.0 <= self.paragraph_page_coverage <= 1.0:
            raise ValueError("paragraph page coverage is invalid")
        if self.paragraph_character_ratio < 0.0:
            raise ValueError("paragraph character ratio is invalid")
        if self.validation_rules != _VALIDATION_RULES:
            raise ValueError("page projection validation rules differ")
        if self.validation_id != _validation_id(self):
            raise ValueError("page projection validation identity differs")


@dataclass(frozen=True)
class OwnerValidatedPageProjection:
    """Typed, text-only projection bound to an owner validation report."""

    plan: PageProjectionPlanEntry
    report: PageProjectionValidationReport
    pages: tuple[PageProjectionPage, ...]

    def __post_init__(self) -> None:
        _require_plan_report_binding(self.plan, self.report)
        if len(self.pages) != self.plan.expected_page_count:
            raise ValueError("page projection page inventory is incomplete")
        if tuple(page.physical_page for page in self.pages) != tuple(
            range(1, len(self.pages) + 1)
        ):
            raise ValueError("page projection pages are unordered")
        if (
            _page_projection_sha256(self.pages)
            != self.report.page_projection_sha256
        ):
            raise ValueError("page projection semantic digest differs")


@dataclass(frozen=True)
class _ParsedProjection:
    pages: tuple[PageProjectionPage, ...]
    paragraph_count: int
    heading_count: int
    figure_count: int
    equation_evidence_count: int
    paragraph_page_count: int
    paragraph_character_count: int
    media_paths: tuple[str, ...]


def validate_page_projection(
    plan: PageProjectionPlanEntry,
    *,
    source_path: Path,
    transcript_path: Path,
    summary_path: Path,
    baseline_path: Path,
    media_root: Path,
) -> OwnerValidatedPageProjection:
    """Validate owner artifacts and return a path-free, typed projection."""

    source = _read_private_regular_file(source_path)
    if hashlib.sha256(source).hexdigest() != plan.source_sha256:
        raise PageProjectionValidationError("source PDF digest differs")
    transcript = _read_private_regular_file(transcript_path)
    summary_content = _read_private_regular_file(summary_path)
    baseline_content = _read_private_regular_file(baseline_path)
    baseline = _json_object(baseline_content, "baseline")
    baseline_pages = _baseline_pages(baseline, plan.expected_page_count)
    parsed = _parse_transcript(
        transcript,
        expected_page_count=plan.expected_page_count,
        printed_page_labels=tuple(
            _optional_string(
                page.get("printed_page_label"), "printed page label"
            )
            for page in baseline_pages
        ),
    )
    media_manifest_sha256 = _validate_media(
        media_root,
        parsed.media_paths,
    )
    summary = _json_object(summary_content, "projection summary")
    _validate_summary(
        summary, parsed, plan.expected_page_count, len(transcript)
    )
    baseline_character_count = sum(
        len(_string_or_empty(page.get("text"))) for page in baseline_pages
    )
    eligible = tuple(
        index
        for index, page in enumerate(baseline_pages)
        if len(_string_or_empty(page.get("text"))) >= 100
    )
    covered = sum(parsed.pages[index].has_paragraph_text for index in eligible)
    coverage = covered / len(eligible) if eligible else 1.0
    character_ratio = (
        parsed.paragraph_character_count / baseline_character_count
        if baseline_character_count
        else 1.0
    )
    if coverage < 0.90:
        raise PageProjectionValidationError(
            f"paragraph page coverage is deficient: {coverage:.4f}"
        )
    if not 0.45 <= character_ratio <= 1.50:
        raise PageProjectionValidationError(
            f"paragraph character coverage is deficient: {character_ratio:.4f}"
        )
    transcript_sha256 = hashlib.sha256(transcript).hexdigest()
    summary_sha256 = hashlib.sha256(summary_content).hexdigest()
    page_projection_sha256 = _page_projection_sha256(parsed.pages)
    paragraph_character_ratio = round(character_ratio, 6)
    paragraph_page_coverage = round(coverage, 6)
    values: dict[str, object] = {
        "document_id": plan.document_id,
        "filename": plan.filename,
        "title": plan.title,
        "source_sha256": plan.source_sha256,
        "transcript_sha256": transcript_sha256,
        "summary_sha256": summary_sha256,
        "media_manifest_sha256": media_manifest_sha256,
        "page_projection_sha256": page_projection_sha256,
        "page_count": plan.expected_page_count,
        "paragraph_count": parsed.paragraph_count,
        "heading_count": parsed.heading_count,
        "figure_count": parsed.figure_count,
        "equation_evidence_count": parsed.equation_evidence_count,
        "media_count": len(parsed.media_paths),
        "paragraph_page_count": parsed.paragraph_page_count,
        "paragraph_character_count": parsed.paragraph_character_count,
        "baseline_character_count": baseline_character_count,
        "eligible_baseline_page_count": len(eligible),
        "covered_baseline_page_count": covered,
        "paragraph_character_ratio": paragraph_character_ratio,
        "paragraph_page_coverage": paragraph_page_coverage,
        "validation_rules": _VALIDATION_RULES,
        "contract_version": PAGE_PROJECTION_CONTRACT_VERSION,
    }
    report = PageProjectionValidationReport(
        validation_id=_validation_id_from_values(values),
        document_id=plan.document_id,
        filename=plan.filename,
        title=plan.title,
        source_sha256=plan.source_sha256,
        transcript_sha256=transcript_sha256,
        summary_sha256=summary_sha256,
        media_manifest_sha256=media_manifest_sha256,
        page_projection_sha256=page_projection_sha256,
        page_count=plan.expected_page_count,
        paragraph_count=parsed.paragraph_count,
        heading_count=parsed.heading_count,
        figure_count=parsed.figure_count,
        equation_evidence_count=parsed.equation_evidence_count,
        media_count=len(parsed.media_paths),
        paragraph_page_count=parsed.paragraph_page_count,
        paragraph_character_count=parsed.paragraph_character_count,
        baseline_character_count=baseline_character_count,
        eligible_baseline_page_count=len(eligible),
        covered_baseline_page_count=covered,
        paragraph_character_ratio=paragraph_character_ratio,
        paragraph_page_coverage=paragraph_page_coverage,
    )
    return OwnerValidatedPageProjection(
        plan=plan, report=report, pages=parsed.pages
    )


def page_projection_validation_report_bytes(
    report: PageProjectionValidationReport,
) -> bytes:
    """Serialize one report to canonical UTF-8 JSON."""

    return (
        json.dumps(
            asdict(report),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def load_page_projection_validation_report(
    path: Path,
) -> PageProjectionValidationReport:
    """Load and identity-check a persisted owner validation report."""

    payload = _json_object(_read_regular_file(path), "validation report")
    try:
        rules = payload["validation_rules"]
        if not isinstance(rules, list) or not all(
            isinstance(item, str) for item in rules
        ):
            raise TypeError("validation rules are malformed")
        return PageProjectionValidationReport(
            validation_id=_required_string(payload, "validation_id"),
            document_id=_required_string(payload, "document_id"),
            filename=_required_string(payload, "filename"),
            title=_required_string(payload, "title"),
            source_sha256=_required_string(payload, "source_sha256"),
            transcript_sha256=_required_string(payload, "transcript_sha256"),
            summary_sha256=_required_string(payload, "summary_sha256"),
            media_manifest_sha256=_required_string(
                payload, "media_manifest_sha256"
            ),
            page_projection_sha256=_required_string(
                payload, "page_projection_sha256"
            ),
            page_count=_required_integer(payload, "page_count"),
            paragraph_count=_required_integer(payload, "paragraph_count"),
            heading_count=_required_integer(payload, "heading_count"),
            figure_count=_required_integer(payload, "figure_count"),
            equation_evidence_count=_required_integer(
                payload, "equation_evidence_count"
            ),
            media_count=_required_integer(payload, "media_count"),
            paragraph_page_count=_required_integer(
                payload, "paragraph_page_count"
            ),
            paragraph_character_count=_required_integer(
                payload, "paragraph_character_count"
            ),
            baseline_character_count=_required_integer(
                payload, "baseline_character_count"
            ),
            eligible_baseline_page_count=_required_integer(
                payload, "eligible_baseline_page_count"
            ),
            covered_baseline_page_count=_required_integer(
                payload, "covered_baseline_page_count"
            ),
            paragraph_character_ratio=_required_number(
                payload, "paragraph_character_ratio"
            ),
            paragraph_page_coverage=_required_number(
                payload, "paragraph_page_coverage"
            ),
            validation_rules=tuple(rules),
            contract_version=_required_string(payload, "contract_version"),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PageProjectionValidationError(
            "validation report is malformed or inconsistent"
        ) from error


def load_owner_validated_page_projection(
    plan: PageProjectionPlanEntry,
    *,
    transcript_path: Path,
    validation_report_path: Path,
) -> OwnerValidatedPageProjection:
    """Load typed text pages without exposing transcript JSON to the caller."""

    report = load_page_projection_validation_report(validation_report_path)
    _require_plan_report_binding(plan, report)
    transcript = _read_regular_file(transcript_path)
    if hashlib.sha256(transcript).hexdigest() != report.transcript_sha256:
        raise PageProjectionValidationError(
            "validated transcript digest differs"
        )
    parsed = _parse_transcript(
        transcript,
        expected_page_count=plan.expected_page_count,
        printed_page_labels=None,
    )
    observed = (
        parsed.paragraph_count,
        parsed.heading_count,
        parsed.figure_count,
        parsed.equation_evidence_count,
        len(parsed.media_paths),
        parsed.paragraph_page_count,
        parsed.paragraph_character_count,
    )
    expected = (
        report.paragraph_count,
        report.heading_count,
        report.figure_count,
        report.equation_evidence_count,
        report.media_count,
        report.paragraph_page_count,
        report.paragraph_character_count,
    )
    if observed != expected:
        raise PageProjectionValidationError(
            "validated transcript counts differ"
        )
    return OwnerValidatedPageProjection(
        plan=plan, report=report, pages=parsed.pages
    )


def iter_page_projection_pages(
    projection: OwnerValidatedPageProjection,
) -> Iterator[PageProjectionPage]:
    """Iterate owner-approved pages in physical-page order."""

    yield from projection.pages


def iter_page_projection_windows(
    projection: OwnerValidatedPageProjection,
    *,
    maximum_pages: int,
) -> Iterator[tuple[PageProjectionPage, ...]]:
    """Group pages without changing page or projection identity."""

    if maximum_pages <= 0 or maximum_pages > _MAXIMUM_PAGES:
        raise ValueError("page projection window bound is invalid")
    for start in range(0, len(projection.pages), maximum_pages):
        yield projection.pages[start : start + maximum_pages]


def _parse_transcript(
    content: bytes,
    *,
    expected_page_count: int,
    printed_page_labels: tuple[str | None, ...] | None,
) -> _ParsedProjection:
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PageProjectionValidationError(
            "transcript is not UTF-8"
        ) from error
    raw_lines = text.splitlines()
    if len(raw_lines) != expected_page_count:
        raise PageProjectionValidationError("transcript page count differs")
    pages: list[PageProjectionPage] = []
    media_paths: list[str] = []
    observed_media_paths: set[str] = set()
    paragraph_count = 0
    heading_count = 0
    figure_count = 0
    equation_count = 0
    paragraph_page_count = 0
    paragraph_character_count = 0
    for physical_page, line in enumerate(raw_lines, 1):
        if len(line.encode("utf-8")) > _MAXIMUM_PAGE_LINE_BYTES:
            raise PageProjectionValidationError(
                "transcript page exceeds its limit"
            )
        page = _json_object(line.encode("utf-8"), "transcript page")
        if _required_integer(page, "physical_page") != physical_page:
            raise PageProjectionValidationError("physical page order differs")
        printed = _optional_string(page.get("printed_page"), "printed page")
        if (
            printed_page_labels is not None
            and printed != printed_page_labels[physical_page - 1]
        ):
            raise PageProjectionValidationError("printed page label differs")
        citation = page.get("citation")
        if not isinstance(citation, dict):
            raise PageProjectionValidationError("page citation is malformed")
        if _required_integer(citation, "physical_page") != physical_page:
            raise PageProjectionValidationError(
                "physical-page citation differs"
            )
        citation_printed = _optional_string(
            citation.get("printed_page"), "citation printed page"
        )
        if citation_printed != printed:
            raise PageProjectionValidationError("printed-page citation differs")
        raw_blocks = page.get("blocks")
        if not isinstance(raw_blocks, list):
            raise PageProjectionValidationError("page blocks are malformed")
        if len(raw_blocks) > _MAXIMUM_BLOCKS_PER_PAGE:
            raise PageProjectionValidationError(
                "page block count exceeds its limit"
            )
        blocks: list[Mapping[str, object]] = []
        for raw_block in raw_blocks:
            if not isinstance(raw_block, dict):
                raise PageProjectionValidationError("page block is malformed")
            blocks.append(raw_block)
        if tuple(
            _required_integer(block, "order") for block in blocks
        ) != tuple(range(len(blocks))):
            raise PageProjectionValidationError("block order is not contiguous")
        paragraph_values = tuple(
            _required_string(block, "text")
            for block in blocks
            if block.get("type") == "paragraph"
        )
        if any(not value.strip() for value in paragraph_values):
            raise PageProjectionValidationError(
                "empty paragraph is not allowed"
            )
        normalized_paragraphs = {_compact(value) for value in paragraph_values}
        text_blocks: list[PageProjectionTextBlock] = []
        page_captions: set[str] = set()
        if paragraph_values:
            paragraph_page_count += 1
        paragraph_count += len(paragraph_values)
        paragraph_character_count += sum(
            len(value) for value in paragraph_values
        )
        for block in blocks:
            kind = block.get("type")
            if kind == "paragraph":
                style = block.get("style")
                if style is not None and not isinstance(style, str):
                    raise PageProjectionValidationError(
                        "paragraph style is malformed"
                    )
                if style not in (None, "heading"):
                    raise PageProjectionValidationError(
                        "paragraph style is unsupported"
                    )
                if style == "heading":
                    heading_count += 1
                text_blocks.append(
                    PageProjectionTextBlock(
                        order=_required_integer(block, "order"),
                        text=_required_string(block, "text"),
                        style=style,
                    )
                )
                continue
            if kind not in ("figure", "equation"):
                raise PageProjectionValidationError(
                    "unsupported page block kind"
                )
            media_path = _relative_media_path(block.get("png_path"))
            if media_path in observed_media_paths:
                raise PageProjectionValidationError(
                    "media path is referenced twice"
                )
            observed_media_paths.add(media_path)
            media_paths.append(media_path)
            if kind == "figure":
                figure_count += 1
                caption = block.get("caption")
                if caption is not None:
                    if not isinstance(caption, str) or not _compact(caption):
                        raise PageProjectionValidationError(
                            "figure caption is malformed"
                        )
                    normalized_caption = _compact(caption)
                    if normalized_caption in page_captions:
                        raise PageProjectionValidationError(
                            "figure caption is duplicated"
                        )
                    page_captions.add(normalized_caption)
                    if normalized_caption in normalized_paragraphs:
                        raise PageProjectionValidationError(
                            "figure caption is projected as a paragraph"
                        )
                    text_blocks.append(
                        PageProjectionTextBlock(
                            order=_required_integer(block, "order"),
                            text=caption,
                            style="caption",
                        )
                    )
                continue
            equation_count += 1
            if (
                block.get("accepted") is not False
                or block.get("review_required") is not True
                or block.get("chunk_text_eligible") is not False
            ):
                raise PageProjectionValidationError(
                    "equation review gate is inconsistent"
                )
            for field in ("native_text", "latex", "mathml"):
                value = block.get(field)
                if (
                    isinstance(value, str)
                    and _compact(value)
                    and _compact(value) in normalized_paragraphs
                ):
                    raise PageProjectionValidationError(
                        "equation evidence is projected as a paragraph"
                    )
        pages.append(
            PageProjectionPage(
                physical_page=physical_page,
                printed_page=printed,
                citation_physical_page=physical_page,
                citation_printed_page=citation_printed,
                text_blocks=tuple(text_blocks),
            )
        )
    return _ParsedProjection(
        pages=tuple(pages),
        paragraph_count=paragraph_count,
        heading_count=heading_count,
        figure_count=figure_count,
        equation_evidence_count=equation_count,
        paragraph_page_count=paragraph_page_count,
        paragraph_character_count=paragraph_character_count,
        media_paths=tuple(media_paths),
    )


def _validate_media(media_root: Path, paths: Sequence[str]) -> str:
    if media_root.is_symlink() or not media_root.is_dir():
        raise PageProjectionValidationError("media root is missing or unsafe")
    records: list[tuple[str, int, str]] = []
    observed_file_identities: set[tuple[int, int]] = set()
    for value in paths:
        relative = PurePosixPath(value)
        current = media_root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise PageProjectionValidationError(
                    "media path contains a symlink"
                )
        try:
            metadata = current.stat(follow_symlinks=False)
        except OSError as error:
            raise PageProjectionValidationError(
                "media artifact could not be inspected"
            ) from error
        file_identity = (metadata.st_dev, metadata.st_ino)
        if file_identity in observed_file_identities:
            raise PageProjectionValidationError(
                "media artifact is referenced through an alias"
            )
        observed_file_identities.add(file_identity)
        content = _read_private_regular_file(current)
        if not content.startswith(_PNG_SIGNATURE):
            raise PageProjectionValidationError("media artifact is not PNG")
        records.append(
            (value, len(content), hashlib.sha256(content).hexdigest())
        )
    return hashlib.sha256(_canonical_json_bytes(records)).hexdigest()


def _validate_summary(
    summary: Mapping[str, object],
    parsed: _ParsedProjection,
    page_count: int,
    transcript_byte_count: int,
) -> None:
    expected = {
        "pages": page_count,
        "paragraphs": parsed.paragraph_count,
        "headings": parsed.heading_count,
        "figures": parsed.figure_count,
        "primary_equations": parsed.equation_evidence_count,
    }
    if summary.get("status") != "complete":
        raise PageProjectionValidationError("projection summary is incomplete")
    for key, value in expected.items():
        if summary.get(key) != value:
            raise PageProjectionValidationError(
                f"projection summary {key} differs"
            )
    if (
        "utf8_bytes" in summary
        and summary["utf8_bytes"] != transcript_byte_count
    ):
        raise PageProjectionValidationError(
            "projection summary byte count differs"
        )


def _baseline_pages(
    baseline: Mapping[str, object], expected_page_count: int
) -> tuple[Mapping[str, object], ...]:
    if baseline.get("complete") is not True:
        raise PageProjectionValidationError("composed baseline is incomplete")
    if baseline.get("page_count") != expected_page_count:
        raise PageProjectionValidationError(
            "composed baseline page count differs"
        )
    raw_pages = baseline.get("pages")
    if not isinstance(raw_pages, list) or len(raw_pages) != expected_page_count:
        raise PageProjectionValidationError(
            "composed baseline pages are incomplete"
        )
    pages: list[Mapping[str, object]] = []
    for page in raw_pages:
        if not isinstance(page, dict):
            raise PageProjectionValidationError(
                "composed baseline page is malformed"
            )
        pages.append(page)
    return tuple(pages)


def _read_private_regular_file(path: Path) -> bytes:
    content = _read_regular_file(path)
    if stat.S_IMODE(path.stat(follow_symlinks=False).st_mode) & 0o077:
        raise PageProjectionValidationError("owner artifact is not private")
    return content


def _read_regular_file(path: Path) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise PageProjectionValidationError("artifact is missing or unsafe")
        size = path.stat(follow_symlinks=False).st_size
        if size > _MAXIMUM_ARTIFACT_BYTES:
            raise PageProjectionValidationError(
                "artifact exceeds its byte limit"
            )
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise PageProjectionValidationError(
                    "artifact is not a regular file"
                )
            content = b""
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                content = stream.read(_MAXIMUM_ARTIFACT_BYTES + 1)
            if len(content) > _MAXIMUM_ARTIFACT_BYTES:
                raise PageProjectionValidationError(
                    "artifact exceeds its byte limit"
                )
            return content
        finally:
            os.close(descriptor)
    except OSError as error:
        raise PageProjectionValidationError(
            "artifact could not be read safely"
        ) from error


def _json_object(content: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(content.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PageProjectionValidationError(
            f"{label} is not valid JSON"
        ) from error
    if not isinstance(value, dict):
        raise PageProjectionValidationError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _relative_media_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PageProjectionValidationError("media path is missing")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in value
        or path.suffix.lower() != ".png"
    ):
        raise PageProjectionValidationError("media path is unsafe")
    canonical = unicodedata.normalize("NFC", path.as_posix())
    if value != canonical:
        raise PageProjectionValidationError("media path is not canonical")
    return canonical


def _required_string(payload: Mapping[str, object], name: str) -> str:
    value = payload[name]
    if not isinstance(value, str) or not value:
        raise TypeError(f"{name} must be a non-empty string")
    return value


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PageProjectionValidationError(f"{name} is malformed")
    return value


def _required_integer(payload: Mapping[str, object], name: str) -> int:
    value = payload[name]
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    return value


def _required_number(payload: Mapping[str, object], name: str) -> float:
    value = payload[name]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{name} must be a number")
    return float(value)


def _string_or_empty(value: object) -> str:
    return value if isinstance(value, str) else ""


def _compact(value: str) -> str:
    return " ".join(value.split())


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _page_projection_sha256(pages: Sequence[PageProjectionPage]) -> str:
    return hashlib.sha256(
        _canonical_json_bytes([asdict(page) for page in pages])
    ).hexdigest()


def _validation_id(report: PageProjectionValidationReport) -> str:
    values = asdict(report)
    del values["validation_id"]
    return _validation_id_from_values(values)


def _validation_id_from_values(values: Mapping[str, object]) -> str:
    ordered = tuple((name, values[name]) for name in sorted(values))
    return stable_id("page-projection-validation", ordered)


def _require_plan_report_binding(
    plan: PageProjectionPlanEntry,
    report: PageProjectionValidationReport,
) -> None:
    if (
        report.document_id != plan.document_id
        or report.filename != plan.filename
        or report.title != plan.title
        or report.source_sha256 != plan.source_sha256
        or report.page_count != plan.expected_page_count
    ):
        raise ValueError("page projection plan and validation report differ")
