#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import argparse
import fcntl
import json
import os
import stat
from io import BytesIO
from pathlib import Path

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
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.models import SourceDocument
from projectkoios.ingestion.pdf.adapters.pymupdf.rendering import (
    PyMuPdfRegionRenderer,
)
from projectkoios.ingestion.pdf.models import PageRegionSelection
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

SOURCE_SHA256 = (
    "539257eb20229bee438dbd628e017bcf8ba6bb6348198ce1e9000cd685d7263e"
)
SOURCE = Path(
    "/Users/eugene/projects/projectkoios/references"
    f"/{SOURCE_SHA256}/document.pdf"
)
PREPARATION = Path(
    "/Users/eugene/projects/projectkoios/artifacts"
    "/reference-multimodal-preparation-v2"
)
CHUNK = PREPARATION / "books/SzeLee3Ed/chunks/chunk-004"
QUALITY = CHUNK / "quality-inventory.json"
INVENTORY = CHUNK / "inventory.json"
RETAINED_EVIDENCE = CHUNK / "figures/figure-001.png"
OUTPUT = Path(
    "/Users/eugene/projects/projectkoios/artifacts"
    "/reference-ollama-multimodal-canary-v1"
)
CANDIDATE_ID = (
    "figure-candidate:sha256:"
    "4f2a63c5f3d25ddd4218bec88770998d2221036584f9efcfa3532bcc521a8296"
)
PAGE_INDEX = 30
BOUNDING_BOX = (243.6750030517578, 72.0, 368.37200927734375, 161.68597412109375)
EVIDENCE_SHA256 = (
    "7148b85feda98a752f50418bca793196ff3c7674c223ee5e1c5e0253f8b7d739"
)
EVIDENCE_BYTES = 20_272
OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
OLLAMA_VERSION = "0.34.3"
OLLAMA_MODEL = "qwen3.5:9b"
OLLAMA_DIGEST = (
    "6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7"
)


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


def identified(path: Path, key: str, namespace: str) -> dict[str, object]:
    value = json.loads(exact(path))
    if type(value) is not dict:
        raise RuntimeError(f"JSON object required: {path}")
    body = dict(value)
    observed = body.pop(key, None)
    if observed != identity(namespace, body):
        raise RuntimeError(f"identity differs: {path}")
    return value


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


def json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


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


def prepare() -> tuple[
    dict[str, object],
    bytes,
    OllamaMultimodalRegionProcessingRequest,
    OllamaMultimodalRegionProcessor,
]:
    source_bytes = exact(SOURCE)
    if len(source_bytes) != 20_143_593 or digest(source_bytes) != SOURCE_SHA256:
        raise RuntimeError("SzeLee3Ed source bytes differ")
    quality = identified(
        QUALITY,
        "quality_inventory_id",
        "reference-multimodal-quality-inventory",
    )
    inventory = identified(
        INVENTORY,
        "inventory_id",
        "reference-multimodal-chunk-inventory",
    )
    quality_figures = quality.get("figures")
    inventory_members = inventory.get("members")
    if type(quality_figures) is not list or any(
        type(value) is not dict for value in quality_figures
    ):
        raise RuntimeError("quality figure records are invalid")
    if type(inventory_members) is not list or any(
        type(value) is not dict for value in inventory_members
    ):
        raise RuntimeError("inventory member records are invalid")
    figures = [
        value
        for value in quality_figures
        if value["candidate_id"] == CANDIDATE_ID
    ]
    members = [
        value
        for value in inventory_members
        if value.get("candidate_id") == CANDIDATE_ID
    ]
    if len(figures) != 1 or len(members) != 1:
        raise RuntimeError("bounded figure evidence is not unique")
    figure = figures[0]
    member = members[0]
    if (
        figure["source_spans"]
        != [{"bounding_box": list(BOUNDING_BOX), "page_index": PAGE_INDEX}]
        or figure["rendered_members"] != ["figures/figure-001.png"]
        or member["path"] != "figures/figure-001.png"
        or member["page_index"] != PAGE_INDEX
        or member["sha256"] != EVIDENCE_SHA256
        or member["bytes"] != EVIDENCE_BYTES
    ):
        raise RuntimeError("bounded figure evidence binding differs")
    retained = exact(RETAINED_EVIDENCE)
    if len(retained) != EVIDENCE_BYTES or digest(retained) != EVIDENCE_SHA256:
        raise RuntimeError("retained figure evidence differs")

    source = SourceDocument.from_bytes(
        source_bytes,
        source_id=f"reference-source:sha256:{SOURCE_SHA256}",
        media_type="application/pdf",
        locator=f"private-reference://{SOURCE_SHA256}",
    )
    selection = PageRegionSelection.for_bounding_box(
        source,
        PAGE_INDEX,
        BOUNDING_BOX,
    )
    regions = PyMuPdfRegionRenderer(max_selections=1).render(
        source,
        BytesIO(source_bytes),
        (selection,),
    )
    if len(regions) != 1:
        raise RuntimeError("bounded render did not return exactly one region")
    region = regions[0]
    if region.content != retained:
        raise RuntimeError("bounded rerender differs from retained evidence")
    request = OllamaMultimodalRegionProcessingRequest.create(
        (OllamaMultimodalSelection.from_rendered_region(region),)
    )
    active_processor = processor()
    processor_identity = active_processor.identity()
    cache_key = OllamaMultimodalCacheKeyIdentity.create(
        request=request,
        processor_identity=processor_identity,
    )
    plan_body = {
        "contract_version": "1.0",
        "authorization_boundary": "explicit_apply_required",
        "selection_count": 1,
        "source_sha256": SOURCE_SHA256,
        "source_bytes": len(source_bytes),
        "book": "SzeLee3Ed",
        "candidate_id": CANDIDATE_ID,
        "quality_inventory_id": quality["quality_inventory_id"],
        "inventory_id": inventory["inventory_id"],
        "page_index": PAGE_INDEX,
        "physical_page": PAGE_INDEX + 1,
        "bounding_box": list(BOUNDING_BOX),
        "rendered_region_id": region.region_id,
        "evidence_sha256": region.content_sha256,
        "evidence_bytes": region.byte_length,
        "width_pixels": region.width_pixels,
        "height_pixels": region.height_pixels,
        "request_id": request.request_id,
        "cache_key": cache_key.cache_key,
        "processor_identity": CanonicalJsonSerializer.project_object(
            processor_identity
        ),
        "task": request.task_kind.value,
        "output_policy": {
            "automated": True,
            "review_status": "unreviewed",
            "accepted": False,
            "chunk_text_eligible": False,
            "publication_eligible": False,
        },
    }
    plan = {
        **plan_body,
        "plan_id": identity(
            "reference-ollama-multimodal-canary-plan", plan_body
        ),
    }
    return plan, retained, request, active_processor


def validate_existing(
    plan: dict[str, object],
) -> dict[str, object] | None:
    result_path = OUTPUT / "result.json"
    summary_path = OUTPUT / "summary.json"
    if not result_path.exists() and not summary_path.exists():
        return None
    if not result_path.exists() or not summary_path.exists():
        raise RuntimeError("partial canary result publication exists")
    result_bytes = exact(result_path)
    result = json.loads(result_bytes)
    if (
        type(result) is not dict
        or result.get("request_id") != plan["request_id"]
        or result.get("evidence_status") != "automated_unreviewed"
        or result.get("determinism") != "nondeterministic"
    ):
        raise RuntimeError("existing canary result binding differs")
    summary = identified(
        summary_path,
        "summary_id",
        "reference-ollama-multimodal-canary-summary",
    )
    if (
        summary["plan_id"] != plan["plan_id"]
        or summary["request_id"] != plan["request_id"]
        or summary["result_id"] != result.get("result_id")
        or summary["result_sha256"] != digest(result_bytes)
        or summary["result_bytes"] != len(result_bytes)
    ):
        raise RuntimeError("existing canary summary binding differs")
    return summary


def run(*, apply: bool) -> dict[str, object]:
    os.umask(0o077)
    private_directory(OUTPUT)
    lock_path = OUTPUT / "run.lock"
    if lock_path.exists() and (
        lock_path.is_symlink()
        or not lock_path.is_file()
        or stat.S_IMODE(lock_path.stat().st_mode) & 0o077
    ):
        raise RuntimeError(f"unsafe run lock: {lock_path}")
    lock_flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        lock_flags |= os.O_NOFOLLOW
    lock_descriptor = os.open(lock_path, lock_flags, 0o600)
    try:
        lock_metadata = os.fstat(lock_descriptor)
        if not stat.S_ISREG(lock_metadata.st_mode) or (
            stat.S_IMODE(lock_metadata.st_mode) & 0o077
        ):
            raise RuntimeError(f"unsafe run lock: {lock_path}")
        fcntl.flock(lock_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan, evidence, request, active_processor = prepare()
        plan_status = create_once(OUTPUT / "plan.json", json_bytes(plan))
        evidence_status = create_once(OUTPUT / "evidence.png", evidence)
        existing = validate_existing(plan)
        if existing is not None:
            return {
                "plan_id": plan["plan_id"],
                "request_id": plan["request_id"],
                "plan_status": plan_status,
                "evidence_status": evidence_status,
                "result_status": "unchanged",
                "model_execution_performed": False,
                "result_id": existing["result_id"],
                "processing_status": existing["processing_status"],
                "cacheable": existing["cacheable"],
            }
        if not apply:
            return {
                "plan_id": plan["plan_id"],
                "request_id": plan["request_id"],
                "plan_status": plan_status,
                "evidence_status": evidence_status,
                "result_status": "not_requested",
                "model_execution_performed": False,
            }

        result = active_processor.action(request=request)
        result_bytes = (
            CanonicalJsonSerializer.serialize_text(result) + "\n"
        ).encode()
        result_status = create_once(OUTPUT / "result.json", result_bytes)
        proposal_count = sum(
            item.proposal is not None for item in result.selection_results
        )
        warning_count = sum(
            len(item.proposal.warnings)
            for item in result.selection_results
            if item.proposal is not None
        )
        summary_body = {
            "contract_version": "1.0",
            "plan_id": plan["plan_id"],
            "request_id": request.request_id,
            "result_id": result.result_id,
            "result_sha256": digest(result_bytes),
            "result_bytes": len(result_bytes),
            "processing_status": result.status.value,
            "cacheable": result.cacheable,
            "proposal_count": proposal_count,
            "warning_count": warning_count,
            "selection_count": len(result.selection_results),
            "model_execution_performed": True,
            "automated": True,
            "review_status": "unreviewed",
            "accepted": False,
            "chunk_text_eligible": False,
            "publication_eligible": False,
        }
        summary = {
            **summary_body,
            "summary_id": identity(
                "reference-ollama-multimodal-canary-summary", summary_body
            ),
        }
        summary_status = create_once(
            OUTPUT / "summary.json", json_bytes(summary)
        )
        output = {
            "plan_id": plan["plan_id"],
            "request_id": request.request_id,
            "result_id": result.result_id,
            "summary_id": summary["summary_id"],
            "plan_status": plan_status,
            "evidence_status": evidence_status,
            "result_status": result_status,
            "summary_status": summary_status,
            "model_execution_performed": True,
            "processing_status": result.status.value,
            "cacheable": result.cacheable,
            "proposal_count": proposal_count,
            "warning_count": warning_count,
        }
        if result.status is not OllamaMultimodalResultStatus.COMPLETE:
            print(json.dumps(output, indent=2, sort_keys=True))
            raise RuntimeError("bounded Ollama canary failed; result retained")
        return output
    finally:
        os.close(lock_descriptor)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one create-once local Ollama multimodal canary"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="invoke the exact configured loopback Ollama model once",
    )
    arguments = parser.parse_args()
    print(json.dumps(run(apply=arguments.apply), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
