#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from projectkoios.ingestion.cache import deserialize_extraction_result
from projectkoios.ingestion.layout import (
    DeterministicLayoutProcessor,
    LayoutConfiguration,
)
from projectkoios.ingestion.serialization import contract_dict
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/ksdft2effmass-manuscript-v1"
)
NATIVE_ROOT = ROOT / "native"
OCR_ROOT = ROOT / "ocr/results-v1"
RECONCILIATION_ROOT = ROOT / "ocr/reconciliation"
BASELINE_PLAN = (
    RECONCILIATION_ROOT / "plans/quality-triage-13-page-pilot-v1.json"
)
BASELINE_INVENTORY = (
    RECONCILIATION_ROOT / "plans/quality-triage-13-page-pilot-v1.inventory.json"
)
BASELINE_REVIEW = (
    RECONCILIATION_ROOT
    / "plans/quality-triage-13-page-pilot-v1.quality-review.json"
)
OUTPUT = RECONCILIATION_ROOT / "mixed-native-reassessment-v1"
LOW_TEXT_UTF8_LIMIT = 40
EXPECTED_DOCUMENTS = 23
EXPECTED_PAGES = 5_232
EXPECTED_EMPTY_PAGES = 425
EXPECTED_MIXED_LOW_TEXT_PAGES = 40
EXPECTED_MIXED_LOW_TEXT_DOCUMENTS = 5
_MAX_EXTRACTION_BYTES = 64_000_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class Candidate:
    source_sha256: str
    source_id: str
    source_blob_id: str
    source_byte_size: int
    extraction_path: Path
    extraction_sha256: str
    extraction_bytes: int
    document_id: str
    manifest_id: str
    page_index: int
    native_text_utf8_bytes: int
    native_text_sha256: str
    native_text_block_ids: tuple[str, ...]


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def digest(content: bytes) -> str:
    return SHA256Fingerprinter.fingerprint(content=content)


def identity(namespace: str, value: object) -> str:
    return f"{namespace}:sha256:{digest(canonical(value))}"


def exact(path: Path, maximum: int) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise RuntimeError(f"missing or unsafe file: {path}") from error
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size <= 0
            or metadata.st_size > maximum
        ):
            raise RuntimeError(f"file size or type is invalid: {path}")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise RuntimeError(f"file is not private: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read(maximum + 1)
        if len(content) != metadata.st_size:
            raise RuntimeError(f"file changed while reading: {path}")
        return content
    finally:
        os.close(descriptor)


def json_object(path: Path, maximum: int) -> tuple[dict[str, object], bytes]:
    content = exact(path, maximum)
    value = json.loads(content)
    if type(value) is not dict:
        raise RuntimeError(f"JSON object required: {path}")
    return value, content


def private_directory(path: Path) -> None:
    if path.exists():
        if path.is_symlink() or not path.is_dir():
            raise RuntimeError(f"unsafe output directory: {path}")
    else:
        path.mkdir(parents=True, mode=0o700)
    os.chmod(path, 0o700)


def create_once(path: Path, content: bytes) -> str:
    if path.exists():
        if exact(path, max(len(content), 1)) != content:
            raise RuntimeError(f"create-once artifact differs: {path}")
        return "unchanged"
    private_directory(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return "created"


def json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def native_text(page: object) -> tuple[str, tuple[str, ...]]:
    blocks = getattr(page, "blocks", None)
    if not isinstance(blocks, tuple):
        raise RuntimeError("extracted page blocks are invalid")
    text_blocks = tuple(
        block
        for block in blocks
        if isinstance(getattr(block, "text", None), str) and block.text
    )
    return (
        "\n".join(block.text for block in text_blocks),
        tuple(block.block_id for block in text_blocks),
    )


def select_candidates(
    candidates: tuple[Candidate, ...],
) -> tuple[Candidate, ...]:
    grouped: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.source_sha256, []).append(candidate)
    selected = [
        sorted(
            values,
            key=lambda item: (-item.native_text_utf8_bytes, item.page_index),
        )[0]
        for _, values in sorted(grouped.items())
    ]
    return tuple(
        sorted(selected, key=lambda item: (item.source_sha256, item.page_index))
    )


def inventory() -> tuple[
    tuple[Candidate, ...],
    dict[str, object],
    dict[str, int],
]:
    candidates: list[Candidate] = []
    document_count = 0
    page_count = 0
    empty_page_count = 0
    extraction_totals: list[dict[str, object]] = []
    for directory in sorted(NATIVE_ROOT.iterdir(), key=lambda path: path.name):
        if (
            directory.is_symlink()
            or not directory.is_dir()
            or not _SHA256.fullmatch(directory.name)
        ):
            continue
        extraction_path = directory / "extraction.json"
        content = exact(extraction_path, _MAX_EXTRACTION_BYTES)
        extraction = deserialize_extraction_result(content.decode("utf-8"))
        source = extraction.document.source
        if (
            source.content_hash != directory.name
            or source.blob_id != f"blob:sha256:{directory.name}"
        ):
            raise RuntimeError("native extraction source binding differs")
        document_count += 1
        page_count += len(extraction.document.pages)
        local_empty = 0
        local_mixed = 0
        for page in extraction.document.pages:
            text, block_ids = native_text(page)
            text_bytes = text.encode()
            byte_count = len(text_bytes)
            if byte_count == 0:
                empty_page_count += 1
                local_empty += 1
            elif byte_count < LOW_TEXT_UTF8_LIMIT:
                local_mixed += 1
                candidates.append(
                    Candidate(
                        source_sha256=directory.name,
                        source_id=source.source_id,
                        source_blob_id=source.blob_id,
                        source_byte_size=source.byte_length,
                        extraction_path=extraction_path,
                        extraction_sha256=digest(content),
                        extraction_bytes=len(content),
                        document_id=extraction.document.document_id,
                        manifest_id=extraction.manifest.manifest_id,
                        page_index=page.page_index,
                        native_text_utf8_bytes=byte_count,
                        native_text_sha256=digest(text_bytes),
                        native_text_block_ids=block_ids,
                    )
                )
        extraction_totals.append(
            {
                "source_sha256": directory.name,
                "page_count": len(extraction.document.pages),
                "empty_page_count": local_empty,
                "mixed_low_text_page_count": local_mixed,
                "extraction_sha256": digest(content),
                "extraction_bytes": len(content),
                "document_id": extraction.document.document_id,
                "manifest_id": extraction.manifest.manifest_id,
            }
        )
    counts = {
        "document_count": document_count,
        "page_count": page_count,
        "empty_page_count": empty_page_count,
        "mixed_low_text_page_count": len(candidates),
        "mixed_low_text_document_count": len(
            {candidate.source_sha256 for candidate in candidates}
        ),
    }
    if counts != {
        "document_count": EXPECTED_DOCUMENTS,
        "page_count": EXPECTED_PAGES,
        "empty_page_count": EXPECTED_EMPTY_PAGES,
        "mixed_low_text_page_count": EXPECTED_MIXED_LOW_TEXT_PAGES,
        "mixed_low_text_document_count": EXPECTED_MIXED_LOW_TEXT_DOCUMENTS,
    }:
        raise RuntimeError("native corpus low-text counts differ")
    corpus_body = {
        "counts": counts,
        "low_text_policy": {
            "text_construction": "nonempty_text_blocks_joined_with_newline",
            "minimum_utf8_bytes_exclusive": 0,
            "maximum_utf8_bytes_exclusive": LOW_TEXT_UTF8_LIMIT,
        },
        "extractions": extraction_totals,
    }
    corpus_inventory = {
        **corpus_body,
        "inventory_id": identity(
            "mixed-native-ocr-candidate-corpus-inventory", corpus_body
        ),
    }
    return tuple(candidates), corpus_inventory, counts


def plan() -> dict[str, object]:
    os.umask(0o077)
    private_directory(OUTPUT)
    baseline_plan = exact(BASELINE_PLAN, 8_000_000)
    baseline_inventory, baseline_inventory_bytes = json_object(
        BASELINE_INVENTORY, 8_000_000
    )
    baseline_review, baseline_review_bytes = json_object(
        BASELINE_REVIEW, 8_000_000
    )
    metrics = baseline_review.get("metrics")
    if (
        baseline_inventory.get("plan_sha256") != digest(baseline_plan)
        or baseline_inventory.get("artifact_count") != 13
        or baseline_inventory.get("native_item_count") != 0
        or baseline_inventory.get("ocr_item_count") != 112
        or baseline_inventory.get("proposed_item_count") != 112
        or type(metrics) is not dict
        or metrics.get("page_count") != 13
        or metrics.get("native_segment_count") != 0
        or metrics.get("match_count") != 0
        or metrics.get("proposal_count") != 112
        or baseline_review.get("acceptance_status")
        != "unaccepted_evidence_only"
        or baseline_review.get("replacement_text_published") is not False
    ):
        raise RuntimeError("retained reconciliation pilot boundary differs")

    candidates, corpus_inventory, counts = inventory()
    selected = select_candidates(candidates)
    if len(selected) != EXPECTED_MIXED_LOW_TEXT_DOCUMENTS:
        raise RuntimeError("mixed-native selection coverage differs")
    processor = DeterministicLayoutProcessor(
        LayoutConfiguration(max_raw_blocks_per_page=2_048)
    )
    selected_records: list[dict[str, object]] = []
    layout_statuses: dict[str, str] = {}
    for candidate in selected:
        extraction_content = exact(
            candidate.extraction_path, _MAX_EXTRACTION_BYTES
        )
        if (
            digest(extraction_content) != candidate.extraction_sha256
            or len(extraction_content) != candidate.extraction_bytes
        ):
            raise RuntimeError("native extraction changed during planning")
        extraction = deserialize_extraction_result(
            extraction_content.decode("utf-8")
        )
        page = extraction.document.pages[candidate.page_index]
        text, block_ids = native_text(page)
        if (
            digest(text.encode()) != candidate.native_text_sha256
            or len(text.encode()) != candidate.native_text_utf8_bytes
            or block_ids != candidate.native_text_block_ids
        ):
            raise RuntimeError("selected native page changed during planning")
        layout = processor.analyze_page(extraction.document.source, page)
        layout_content = json_bytes(contract_dict(layout))
        relative_layout = (
            Path("layout")
            / candidate.source_sha256
            / f"page-{candidate.page_index + 1:06d}.json"
        )
        layout_statuses[relative_layout.as_posix()] = create_once(
            OUTPUT / relative_layout, layout_content
        )
        ocr_relative = (
            Path(candidate.source_sha256)
            / f"page-{candidate.page_index + 1:06d}"
            / "result.json"
        )
        reconciliation_relative = ocr_relative
        if os.path.lexists(OCR_ROOT / ocr_relative) or os.path.lexists(
            RECONCILIATION_ROOT / "results-v1" / reconciliation_relative
        ):
            raise RuntimeError(
                "selected mixed-native page already has retained OCR or reconciliation"
            )
        record_body = {
            "source_sha256": candidate.source_sha256,
            "source_id": candidate.source_id,
            "source_blob_id": candidate.source_blob_id,
            "source_byte_size": candidate.source_byte_size,
            "extraction_path": candidate.extraction_path.relative_to(
                ROOT
            ).as_posix(),
            "extraction_sha256": candidate.extraction_sha256,
            "extraction_bytes": candidate.extraction_bytes,
            "document_id": candidate.document_id,
            "manifest_id": candidate.manifest_id,
            "page_index": candidate.page_index,
            "native_text_utf8_bytes": candidate.native_text_utf8_bytes,
            "native_text_sha256": candidate.native_text_sha256,
            "native_text_block_ids": list(candidate.native_text_block_ids),
            "layout_evidence_path": relative_layout.as_posix(),
            "layout_evidence_sha256": digest(layout_content),
            "layout_evidence_bytes": len(layout_content),
            "layout_result_id": layout.result_id,
            "layout_configuration_digest": layout.configuration_digest,
            "layout_proposed_order": list(layout.proposed_order),
            "ocr_publication_status": "not_requested",
            "reconciliation_publication_status": "not_requested",
        }
        selected_records.append(
            {
                **record_body,
                "selection_id": identity(
                    "mixed-native-ocr-reassessment-selection", record_body
                ),
            }
        )

    body = {
        "contract_version": "1.0",
        "scope": "plan_only_mixed_native_ocr_reconciliation_reassessment",
        "authorization": "reassessment_only_no_ocr_or_reconciliation_execution",
        "retained_ocr_only_pilot": {
            "plan_sha256": digest(baseline_plan),
            "inventory_sha256": digest(baseline_inventory_bytes),
            "quality_review_sha256": digest(baseline_review_bytes),
            "page_count": 13,
            "native_segment_count": 0,
            "ocr_item_count": 112,
            "proposed_item_count": 112,
            "match_count": 0,
            "validated_scope": "ocr_only_publication_and_replay",
            "mixed_native_path_validated": False,
        },
        "candidate_corpus_inventory": corpus_inventory,
        "candidate_counts": counts,
        "selection_policy": {
            "name": "one_maximum_native_text_page_per_affected_document",
            "tie_breaker": "lowest_page_index",
            "selected_document_count": len(selected_records),
            "selected_page_count": len(selected_records),
        },
        "selected_pages": selected_records,
        "readiness": {
            "exact_native_extraction_bound": True,
            "exact_native_text_block_ids_bound": True,
            "exact_layout_evidence_materialized": True,
            "selective_ocr_plan_supports_native_references": True,
            "retained_mixed_native_ocr_publications_available": False,
            "reconciliation_plan_v1_supports_mixed_native": False,
            "reconciliation_plan_v2_required": True,
            "future_plan_must_bind_native_page_and_layout_evidence": True,
            "future_ocr_execution_requires_separate_authorization": True,
            "future_reconciliation_execution_requires_separate_authorization": True,
        },
        "status": "blocked_pending_contract_and_separate_execution_authorization",
        "ocr_execution_performed": False,
        "reconciliation_execution_performed": False,
        "replacement_text_composed": False,
        "search_indexing_performed": False,
        "publication_performed": False,
        "automated": True,
        "review_status": "unreviewed",
        "accepted": False,
        "chunk_text_eligible": False,
        "execution_authorized": False,
    }
    artifact = {
        **body,
        "reassessment_id": identity(
            "mixed-native-ocr-reconciliation-reassessment", body
        ),
    }
    content = json_bytes(artifact)
    plan_status = create_once(OUTPUT / "plan.json", content)
    return {
        "reassessment_id": artifact["reassessment_id"],
        "plan_sha256": digest(content),
        "plan_bytes": len(content),
        "plan_status": plan_status,
        "layout_statuses": dict(sorted(layout_statuses.items())),
        "mixed_low_text_page_count": counts["mixed_low_text_page_count"],
        "mixed_low_text_document_count": counts[
            "mixed_low_text_document_count"
        ],
        "selected_page_count": len(selected_records),
        "ocr_execution_performed": False,
        "reconciliation_execution_performed": False,
        "execution_authorized": False,
    }


def main() -> None:
    print(json.dumps(plan(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
