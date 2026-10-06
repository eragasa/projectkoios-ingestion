#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import argparse
import fcntl
import json
import os
import stat
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any

from projectkoios.ingestion import (
    DeterministicFigureCandidateDetector,
    DeterministicLayoutProcessor,
    DeterministicTableCandidateDetector,
    FigureDetectionConfiguration,
    LayoutConfiguration,
    PageRegionSelection,
    PyMuPdfExtractor,
    SourceDocument,
    TableDetectionConfiguration,
)
from projectkoios.ingestion.integrations.ollama.base import OllamaRequestOptions
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMultimodalConfiguration,
    OllamaMultimodalLimits,
    OllamaMultimodalResultStatus,
    OllamaMultimodalSelection,
)
from projectkoios.ingestion.integrations.ollama.multimodal.cache.identity import (
    OllamaMultimodalCacheKeyIdentity,
)
from projectkoios.ingestion.integrations.ollama.multimodal.processor.region.base import (
    OllamaMultimodalRegionProcessor,
)
from projectkoios.ingestion.integrations.ollama.multimodal.processor.region.request import (
    OllamaMultimodalRegionProcessingRequest,
)
from projectkoios.ingestion.pdf.adapters.pymupdf.rendering import (
    PyMuPdfRegionRenderer,
)
from projectkoios.ingestion.pdf.models import RenderedRegion
from projectkoios.ingestion.pdf.private_page_span.reference import (
    PrivatePdfPageSpanReference,
)
from projectkoios.ingestion.serialization import (
    contract_dict,
    serialize_contract,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

PREPARATION = Path(
    "/Users/eugene/projects/projectkoios/artifacts"
    "/reference-multimodal-preparation-v2"
)
OUTPUT = Path(
    "/Users/eugene/projects/projectkoios/artifacts"
    "/reference-ollama-multimodal-replicated-canary-v1"
)
PLAN_PATH = OUTPUT / "plan.json"
OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
OLLAMA_VERSION = "0.34.3"
OLLAMA_MODEL = "qwen3.5:9b"
OLLAMA_DIGEST = (
    "6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7"
)


@dataclass(frozen=True, slots=True)
class PreparedSample:
    sample_id: str
    sample_key: str
    request: OllamaMultimodalRegionProcessingRequest
    cache_key: str
    region_id: str
    selection_id: str


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


def integer(value: object, description: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"integer required: {description}")
    return value


def text(value: object, description: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"text required: {description}")
    return value


def relative_path(value: object, description: str) -> Path:
    parsed = PurePosixPath(text(value, description))
    if (
        parsed.is_absolute()
        or not parsed.parts
        or any(part in ("", ".", "..") for part in parsed.parts)
    ):
        raise RuntimeError(f"safe relative path required: {description}")
    return Path(*parsed.parts)


def exact(path: Path) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise RuntimeError(f"missing or unsafe file: {path}") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError(f"missing or unsafe file: {path}")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise RuntimeError(f"file is not private: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read()
        if len(content) != metadata.st_size:
            raise RuntimeError(f"file changed while reading: {path}")
        return content
    finally:
        os.close(descriptor)


def json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def identified_bytes(
    content: bytes, key: str, namespace: str, description: str
) -> dict[str, object]:
    value = json.loads(content)
    if type(value) is not dict:
        raise RuntimeError(f"JSON object required: {description}")
    body = dict(value)
    observed = body.pop(key, None)
    if observed != identity(namespace, body):
        raise RuntimeError(f"identity differs: {description}")
    return value


def identified(path: Path, key: str, namespace: str) -> dict[str, object]:
    return identified_bytes(exact(path), key, namespace, str(path))


def private_directory(path: Path) -> None:
    if path.exists():
        if path.is_symlink() or not path.is_dir():
            raise RuntimeError(f"unsafe output directory: {path}")
    else:
        path.mkdir(parents=True, mode=0o700)
    os.chmod(path, 0o700)


def create_once(path: Path, content: bytes) -> str:
    if path.exists():
        if exact(path) != content:
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


def processor() -> OllamaMultimodalRegionProcessor:
    return OllamaMultimodalRegionProcessor(
        configuration=OllamaMultimodalConfiguration(
            endpoint=OLLAMA_ENDPOINT,
            model_name=OLLAMA_MODEL,
            expected_model_digest=OLLAMA_DIGEST,
            expected_ollama_version=OLLAMA_VERSION,
            options=OllamaRequestOptions(
                temperature=0.0,
                seed=0,
                context_tokens=8192,
                output_tokens=2048,
                keep_alive="0",
            ),
            limits=OllamaMultimodalLimits(max_selections=1),
            connect_timeout_seconds=5.0,
            read_timeout_seconds=300.0,
        )
    )


def validate_plan(plan: dict[str, object]) -> None:
    samples = plan.get("samples")
    invocations = plan.get("invocations")
    output_policy = plan.get("output_policy")
    comparison_policy = plan.get("comparison_policy")
    if (
        plan.get("contract_version") != "1.0"
        or plan.get("authorization") != "plan_only_no_model_execution"
        or plan.get("model_determinism") != "nondeterministic"
        or plan.get("model_execution_performed") is not False
        or plan.get("sample_count") != 3
        or plan.get("replicates_per_sample") != 2
        or plan.get("planned_invocation_count") != 6
        or type(samples) is not list
        or len(samples) != 3
        or any(type(item) is not dict for item in samples)
        or type(invocations) is not list
        or len(invocations) != 6
        or any(type(item) is not dict for item in invocations)
        or output_policy
        != {
            "accepted": False,
            "automated": True,
            "chunk_text_eligible": False,
            "publication_eligible": False,
            "review_status": "unreviewed",
        }
        or type(comparison_policy) is not dict
        or comparison_policy.get("no_determinism_claim") is not True
    ):
        raise RuntimeError("replicated canary plan boundary differs")
    sample_ids = {item.get("sample_id") for item in samples}
    if len(sample_ids) != 3 or None in sample_ids:
        raise RuntimeError("replicated canary sample identities differ")
    evidence_paths: set[Path] = set()
    for sample in samples:
        sample_body = dict(sample)
        observed_sample_id = sample_body.pop("sample_id")
        evidence_path = relative_path(
            sample.get("retained_evidence_path"), "retained evidence path"
        )
        if (
            observed_sample_id
            != identity(
                "reference-ollama-multimodal-replicated-canary-sample",
                sample_body,
            )
            or evidence_path in evidence_paths
            or evidence_path.parts[0] != "evidence"
        ):
            raise RuntimeError("replicated canary sample binding differs")
        evidence_paths.add(evidence_path)
    invocation_ids = {item.get("invocation_id") for item in invocations}
    if len(invocation_ids) != 6 or None in invocation_ids:
        raise RuntimeError("replicated canary invocation identities differ")
    result_paths: set[Path] = set()
    for invocation in invocations:
        body = dict(invocation)
        observed = body.pop("invocation_id")
        result_path = relative_path(
            invocation.get("result_path"), "invocation result path"
        )
        if result_path in result_paths or result_path.parts[0] != "results":
            raise RuntimeError("replicated canary result path differs")
        result_paths.add(result_path)
        if (
            observed
            != identity(
                "reference-ollama-multimodal-replicated-canary-invocation",
                body,
            )
            or invocation.get("sample_id") not in sample_ids
            or invocation.get("execution_status") != "not_requested"
            or invocation.get("cache_policy")
            != "independent_invocation_no_cross_replicate_reuse"
        ):
            raise RuntimeError("replicated canary invocation binding differs")


def filtered_document(content: bytes, source: SourceDocument) -> Any:
    extraction = PyMuPdfExtractor(maximum_pages=10).extract(
        source, BytesIO(content)
    )
    pages = []
    for page in extraction.document.pages:
        blocks = []
        for block in page.blocks:
            valid = all(
                span.bounding_box is None
                or (
                    0.0
                    <= span.bounding_box[0]
                    <= span.bounding_box[2]
                    <= page.width
                    and 0.0
                    <= span.bounding_box[1]
                    <= span.bounding_box[3]
                    <= page.height
                )
                for span in block.source_spans
            )
            if valid or block.kind != "text":
                blocks.append(block)
        pages.append(replace(page, blocks=tuple(blocks)))
    return replace(extraction.document, pages=tuple(pages))


def visual_box(candidate: Any) -> tuple[float, float, float, float]:
    boxes = [
        component.source_bounding_box for component in candidate.components
    ]
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def reconstruct_regions(
    plan: dict[str, object],
) -> dict[str, RenderedRegion]:
    samples = plan["samples"]
    if type(samples) is not list:
        raise RuntimeError("plan samples are invalid")
    grouped: dict[tuple[str, int], list[dict[str, object]]] = {}
    for sample in samples:
        if type(sample) is not dict:
            raise RuntimeError("plan sample is invalid")
        key = (str(sample["book"]), int(sample["chunk_number"]))
        grouped.setdefault(key, []).append(sample)

    regions: dict[str, RenderedRegion] = {}
    for (book, chunk_number), chunk_samples in grouped.items():
        chunk_root = (
            PREPARATION
            / "books"
            / book
            / "chunks"
            / f"chunk-{chunk_number:03d}"
        )
        inventory = identified(
            chunk_root / "inventory.json",
            "inventory_id",
            "reference-multimodal-chunk-inventory",
        )
        content = exact(chunk_root / "source.pdf")
        if (
            inventory.get("book") != book
            or inventory.get("chunk_number") != chunk_number
            or inventory.get("chunk_pdf_sha256") != digest(content)
            or inventory.get("chunk_pdf_bytes") != len(content)
        ):
            raise RuntimeError(f"{book} chunk {chunk_number}: source differs")
        first = integer(inventory["first_page_index"], "first page index")
        last = integer(
            inventory["last_page_index_exclusive"],
            "last page index exclusive",
        )
        reference = PrivatePdfPageSpanReference.create(
            owner=book,
            first_page_number=first + 1,
            last_page_number=last,
        )
        source = SourceDocument.from_bytes(
            content,
            source_id=reference.source_id,
            media_type="application/pdf",
            locator=reference.locator,
        )
        document = filtered_document(content, source)
        layouts = DeterministicLayoutProcessor(
            LayoutConfiguration(max_raw_blocks_per_page=2_048)
        ).analyze(document)
        figure_samples = [
            sample
            for sample in chunk_samples
            if sample.get("evidence_class") == "figure"
        ]
        if figure_samples:
            figure_detection = DeterministicFigureCandidateDetector(
                FigureDetectionConfiguration(
                    minimum_embedded_dimension_points=12.0,
                    minimum_embedded_area_points=576.0,
                ),
                region_renderer=PyMuPdfRegionRenderer(
                    max_total_pixels=100_000_000,
                    max_total_raster_bytes=100_000_000,
                ),
            ).detect_with_layout(document, BytesIO(content), layouts)
            figure_candidates = {
                candidate.candidate_id: candidate
                for candidate in figure_detection.candidates
            }
            final_renderer = PyMuPdfRegionRenderer(
                max_total_pixels=25_000_000,
                max_total_raster_bytes=100_000_000,
            )
            for sample in figure_samples:
                figure_candidate = figure_candidates.get(
                    text(sample["candidate_id"], "figure candidate identity")
                )
                if figure_candidate is None:
                    raise RuntimeError(
                        f"{sample['sample_key']}: figure candidate missing"
                    )
                box = visual_box(figure_candidate)
                region = final_renderer.render(
                    source,
                    BytesIO(content),
                    (
                        PageRegionSelection.for_bounding_box(
                            source,
                            figure_candidate.source_spans[0].page_index,
                            box,
                        ),
                    ),
                )[0]
                regions[str(sample["sample_id"])] = region

        table_samples = [
            sample
            for sample in chunk_samples
            if sample.get("evidence_class") == "table"
        ]
        if table_samples:
            table_detection = DeterministicTableCandidateDetector(
                TableDetectionConfiguration(),
                region_renderer=PyMuPdfRegionRenderer(
                    max_total_pixels=100_000_000,
                    max_total_raster_bytes=100_000_000,
                ),
            ).detect_with_layout(document, BytesIO(content), layouts)
            table_candidates = {
                candidate.candidate_id: candidate
                for candidate in table_detection.candidates
            }
            for sample in table_samples:
                table_candidate = table_candidates.get(
                    text(sample["candidate_id"], "table candidate identity")
                )
                if table_candidate is None:
                    raise RuntimeError(
                        f"{sample['sample_key']}: table candidate missing"
                    )
                matching = [
                    region.rendered_region
                    for region in table_candidate.regions
                    if region.rendered_region.content_sha256
                    == sample["evidence_sha256"]
                ]
                if len(matching) != 1:
                    raise RuntimeError(
                        f"{sample['sample_key']}: table region not unique"
                    )
                regions[str(sample["sample_id"])] = matching[0]
    return regions


def prepare() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, PreparedSample],
    OllamaMultimodalRegionProcessor,
]:
    plan = identified(
        PLAN_PATH,
        "plan_id",
        "reference-ollama-multimodal-replicated-canary-plan",
    )
    validate_plan(plan)
    active_processor = processor()
    processor_record = contract_dict(active_processor.identity())
    if processor_record != plan["processor_identity"]:
        raise RuntimeError("replicated canary processor identity differs")
    regions = reconstruct_regions(plan)
    prepared: dict[str, PreparedSample] = {}
    manifest_samples: list[dict[str, object]] = []
    samples = plan["samples"]
    if type(samples) is not list:
        raise RuntimeError("plan samples are invalid")
    for sample in samples:
        if type(sample) is not dict:
            raise RuntimeError("plan sample is invalid")
        sample_id = str(sample["sample_id"])
        region = regions.get(sample_id)
        if region is None:
            raise RuntimeError(f"{sample['sample_key']}: region missing")
        evidence = exact(
            OUTPUT
            / relative_path(
                sample["retained_evidence_path"], "retained evidence path"
            )
        )
        if (
            region.content != evidence
            or region.content_sha256 != sample["evidence_sha256"]
            or region.byte_length != sample["evidence_bytes"]
            or region.width_pixels != sample["width_pixels"]
            or region.height_pixels != sample["height_pixels"]
            or region.page_index + int(sample["chunk_number"] - 1) * 10
            != sample["page_index"]
        ):
            raise RuntimeError(f"{sample['sample_key']}: rerender differs")
        selection = OllamaMultimodalSelection.from_rendered_region(region)
        request = OllamaMultimodalRegionProcessingRequest.create((selection,))
        cache_key = OllamaMultimodalCacheKeyIdentity.create(
            request=request,
            processor_identity=active_processor.identity(),
        ).cache_key
        prepared[sample_id] = PreparedSample(
            sample_id=sample_id,
            sample_key=str(sample["sample_key"]),
            request=request,
            cache_key=cache_key,
            region_id=region.region_id,
            selection_id=selection.selection_id,
        )
        manifest_samples.append(
            {
                "sample_id": sample_id,
                "sample_key": sample["sample_key"],
                "request_id": request.request_id,
                "cache_key": cache_key,
                "selection_id": selection.selection_id,
                "region_id": region.region_id,
                "source_id": region.source_id,
                "source_blob_id": region.source_blob_id,
                "source_content_hash": region.source_content_hash,
                "local_page_index": region.page_index,
                "global_page_index": sample["page_index"],
                "evidence_sha256": region.content_sha256,
                "evidence_bytes": region.byte_length,
            }
        )

    invocations = plan["invocations"]
    if type(invocations) is not list:
        raise RuntimeError("plan invocations are invalid")
    manifest_invocations = []
    for invocation in invocations:
        if type(invocation) is not dict:
            raise RuntimeError("plan invocation is invalid")
        item = prepared.get(str(invocation["sample_id"]))
        if item is None:
            raise RuntimeError("invocation references an unknown sample")
        result_path = relative_path(
            invocation["result_path"], "invocation result path"
        )
        receipt_path = Path("receipts", *result_path.parts[1:])
        manifest_invocations.append(
            {
                "invocation_id": invocation["invocation_id"],
                "sample_id": item.sample_id,
                "sample_key": item.sample_key,
                "replicate_ordinal": invocation["replicate_ordinal"],
                "request_id": item.request.request_id,
                "cache_key": item.cache_key,
                "cache_policy": invocation["cache_policy"],
                "result_path": result_path.as_posix(),
                "receipt_path": receipt_path.as_posix(),
            }
        )
    manifest_body = {
        "contract_version": "1.0",
        "plan_id": plan["plan_id"],
        "processor_identity": processor_record,
        "samples": manifest_samples,
        "invocations": manifest_invocations,
        "model_determinism": "nondeterministic",
        "model_execution_performed": False,
    }
    manifest = {
        **manifest_body,
        "manifest_id": identity(
            "reference-ollama-multimodal-replicated-canary-request-manifest",
            manifest_body,
        ),
    }
    return plan, manifest, prepared, active_processor


def result_receipt(
    plan: dict[str, object],
    manifest: dict[str, object],
    invocation: dict[str, object],
    result_bytes: bytes,
) -> dict[str, object]:
    result = json.loads(result_bytes)
    if type(result) is not dict:
        raise RuntimeError("Ollama result is not a JSON object")
    if (
        result.get("request_id") != invocation["request_id"]
        or result.get("evidence_status") != "automated_unreviewed"
        or result.get("determinism") != "nondeterministic"
        or not isinstance(result.get("result_id"), str)
        or type(result.get("selection_results")) is not list
    ):
        raise RuntimeError("Ollama result binding differs")
    proposals = []
    warning_count = 0
    for selection in result["selection_results"]:
        if type(selection) is not dict:
            raise RuntimeError("Ollama selection result is invalid")
        proposal = selection.get("proposal")
        if proposal is not None:
            if type(proposal) is not dict:
                raise RuntimeError("Ollama proposal is invalid")
            warnings = proposal.get("warnings")
            if type(warnings) is not list:
                raise RuntimeError("Ollama proposal warnings are invalid")
            warning_count += len(warnings)
            proposals.append(
                {
                    "selection_id": selection.get("selection_id"),
                    "text_sha256": proposal.get("text_sha256"),
                    "text_utf8_byte_length": proposal.get(
                        "text_utf8_byte_length"
                    ),
                    "warning_count": len(warnings),
                }
            )
    body = {
        "contract_version": "1.0",
        "plan_id": plan["plan_id"],
        "manifest_id": manifest["manifest_id"],
        "invocation_id": invocation["invocation_id"],
        "sample_id": invocation["sample_id"],
        "replicate_ordinal": invocation["replicate_ordinal"],
        "request_id": invocation["request_id"],
        "cache_key": invocation["cache_key"],
        "result_id": result["result_id"],
        "result_sha256": digest(result_bytes),
        "result_bytes": len(result_bytes),
        "processing_status": result.get("status"),
        "cacheable": result.get("cacheable"),
        "proposals": proposals,
        "warning_count": warning_count,
        "model_execution_performed": True,
        "model_determinism": "nondeterministic",
        "automated": True,
        "review_status": "unreviewed",
        "accepted": False,
        "chunk_text_eligible": False,
        "publication_eligible": False,
    }
    return {
        **body,
        "receipt_id": identity(
            "reference-ollama-multimodal-replicated-canary-receipt", body
        ),
    }


def existing_or_execute(
    *,
    plan: dict[str, object],
    manifest: dict[str, object],
    invocation: dict[str, object],
    prepared: PreparedSample,
    active_processor: OllamaMultimodalRegionProcessor,
    apply: bool,
) -> tuple[str, dict[str, object] | None, bool]:
    result_path = OUTPUT / relative_path(
        invocation["result_path"], "result path"
    )
    receipt_path = OUTPUT / relative_path(
        invocation["receipt_path"], "receipt path"
    )
    if receipt_path.exists() and not result_path.exists():
        raise RuntimeError("receipt exists without its result")
    if result_path.exists():
        result_bytes = exact(result_path)
        receipt = result_receipt(plan, manifest, invocation, result_bytes)
        create_once(receipt_path, json_bytes(receipt))
        return "unchanged", receipt, False
    if not apply:
        return "not_requested", None, False
    result = active_processor.action(request=prepared.request)
    result_bytes = (serialize_contract(result) + "\n").encode()
    status = create_once(result_path, result_bytes)
    receipt = result_receipt(plan, manifest, invocation, result_bytes)
    create_once(receipt_path, json_bytes(receipt))
    return status, receipt, True


def final_summary(
    plan: dict[str, object],
    manifest: dict[str, object],
    receipts: list[dict[str, object]],
) -> dict[str, object]:
    records = [
        {
            "invocation_id": receipt["invocation_id"],
            "receipt_id": receipt["receipt_id"],
            "sample_id": receipt["sample_id"],
            "replicate_ordinal": receipt["replicate_ordinal"],
            "request_id": receipt["request_id"],
            "result_id": receipt["result_id"],
            "result_sha256": receipt["result_sha256"],
            "processing_status": receipt["processing_status"],
            "proposals": receipt["proposals"],
            "warning_count": receipt["warning_count"],
        }
        for receipt in receipts
    ]
    body = {
        "contract_version": "1.0",
        "plan_id": plan["plan_id"],
        "manifest_id": manifest["manifest_id"],
        "invocation_count": len(records),
        "records": records,
        "model_determinism": "nondeterministic",
        "fresh_inference_reproducible": False,
        "automated": True,
        "review_status": "unreviewed",
        "accepted": False,
        "chunk_text_eligible": False,
        "publication_eligible": False,
    }
    return {
        **body,
        "summary_id": identity(
            "reference-ollama-multimodal-replicated-canary-summary", body
        ),
    }


def run(*, apply_plan_id: str | None) -> dict[str, object]:
    os.umask(0o077)
    private_directory(OUTPUT)
    lock_path = OUTPUT / "execution.lock"
    if lock_path.exists() and (
        lock_path.is_symlink()
        or not lock_path.is_file()
        or stat.S_IMODE(lock_path.stat().st_mode) & 0o077
    ):
        raise RuntimeError(f"unsafe execution lock: {lock_path}")
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(lock_path, flags, 0o600)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or (
            stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise RuntimeError(f"unsafe execution lock: {lock_path}")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan, manifest, prepared, active_processor = prepare()
        manifest_status = create_once(
            OUTPUT / "request-manifest.json", json_bytes(manifest)
        )
        if apply_plan_id is not None and apply_plan_id != plan["plan_id"]:
            raise RuntimeError("--apply plan identity differs")
        apply = apply_plan_id is not None
        manifest_invocations = manifest["invocations"]
        if type(manifest_invocations) is not list:
            raise RuntimeError("request manifest invocations are invalid")
        statuses: dict[str, str] = {}
        receipts: list[dict[str, object]] = []
        executions = 0
        for invocation in manifest_invocations:
            if type(invocation) is not dict:
                raise RuntimeError("request manifest invocation is invalid")
            item = prepared.get(str(invocation["sample_id"]))
            if item is None:
                raise RuntimeError("prepared request is missing")
            status, receipt, executed = existing_or_execute(
                plan=plan,
                manifest=manifest,
                invocation=invocation,
                prepared=item,
                active_processor=active_processor,
                apply=apply,
            )
            statuses[str(invocation["invocation_id"])] = status
            executions += int(executed)
            if receipt is not None:
                receipts.append(receipt)
                if receipt["processing_status"] != (
                    OllamaMultimodalResultStatus.COMPLETE.value
                ):
                    raise RuntimeError(
                        "Ollama invocation failed; result retained without retry"
                    )
        summary_status = "not_ready"
        summary_id = None
        if len(receipts) == len(manifest_invocations):
            summary = final_summary(plan, manifest, receipts)
            summary_status = create_once(
                OUTPUT / "execution-summary.json", json_bytes(summary)
            )
            summary_id = summary["summary_id"]
        return {
            "plan_id": plan["plan_id"],
            "manifest_id": manifest["manifest_id"],
            "manifest_status": manifest_status,
            "planned_invocation_count": len(manifest_invocations),
            "retained_result_count": len(receipts),
            "invocation_statuses": statuses,
            "summary_status": summary_status,
            "summary_id": summary_id,
            "model_determinism": "nondeterministic",
            "model_executions_performed": executions,
            "execution_requested": apply,
        }
    finally:
        os.close(descriptor)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Reconstruct the frozen replicated Ollama requests; execution "
            "requires --apply with the exact plan identity"
        )
    )
    parser.add_argument(
        "--apply",
        metavar="PLAN_ID",
        help=(
            "execute missing create-once slots only when PLAN_ID exactly "
            "matches the frozen plan"
        ),
    )
    arguments = parser.parse_args()
    print(
        json.dumps(run(apply_plan_id=arguments.apply), indent=2, sort_keys=True)
    )


if __name__ == "__main__":
    main()
