#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import json
import os
import runpy
import time
from pathlib import Path

from projectkoios.ingestion import (
    EquationAssemblyResult,
)
from projectkoios.ingestion.equations.assembly.identity import (
    EQUATION_ASSEMBLY_CONTRACT_VERSION,
)
from projectkoios.ingestion.equations.recognition.request import (
    EquationRecognitionRequest,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.pix2tex.recognizer import (
    Pix2TexCliEquationRecognizer,
)
from projectkoios.ingestion.integrations.pix2tex.resource import (
    Pix2TexResourceBinding,
)
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-preparation-v2"
)
CANARY_ROOT = ROOT / "pix2tex-canary-v1"
REFERENCES = Path("/Users/eugene/projects/projectkoios/references")
QUALITY_SCRIPT = (
    Path(__file__).resolve().parent
    / "007.build_pending_reference_candidate_quality.py"
)
PIX2TEX_ROOT = Path(
    "/Users/eugene/.local/share/uv/tools/pix2tex/lib/python3.12/site-packages/pix2tex/model"
)
PIX2TEX_EXE = Path("/Users/eugene/.local/bin/pix2tex_cli")
PIX2TEX_RESOURCES = (
    Pix2TexResourceBinding(
        name="configuration", path=PIX2TEX_ROOT / "settings/config.yaml"
    ),
    Pix2TexResourceBinding(
        name="tokenizer", path=PIX2TEX_ROOT / "dataset/tokenizer.json"
    ),
    Pix2TexResourceBinding(
        name="model", path=PIX2TEX_ROOT / "checkpoints/weights.pth"
    ),
    Pix2TexResourceBinding(
        name="image-resizer",
        path=PIX2TEX_ROOT / "checkpoints/image_resizer.pth",
    ),
)
QUANTILES = (0.0, 0.25, 0.5, 0.75, 1.0, 0.0, 0.25, 0.5, 0.75, 1.0)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()


def digest(content: bytes) -> str:
    return SHA256Fingerprinter.fingerprint(content=content)


def identity(namespace: str, value: object) -> str:
    return f"{namespace}:sha256:{digest(canonical(value))}"


def exact(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"missing or unsafe file: {path}")
    return path.read_bytes()


def create_once(path: Path, content: bytes) -> str:
    if path.exists():
        if exact(path) != content:
            raise RuntimeError(f"create-once artifact differs: {path}")
        return "unchanged"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return "created"


def json_once(path: Path, value: object) -> str:
    return create_once(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n",
    )


def recognizer() -> Pix2TexCliEquationRecognizer:
    return Pix2TexCliEquationRecognizer(
        PIX2TEX_EXE,
        backend_version="0.1.4",
        resources=PIX2TEX_RESOURCES,
        timeout_seconds=900,
    )


def select_canary(items: list[dict[str, object]]) -> list[dict[str, object]]:
    selected = []
    books = sorted({str(item["book"]) for item in items})
    for book in books:
        candidates = sorted(
            (item for item in items if item["book"] == book),
            key=lambda item: (
                int(item["page_index"]),
                str(item["assembly_id"]),
            ),
        )
        if len(candidates) < 10:
            raise RuntimeError(f"{book}: fewer than ten primary candidates")
        for stratum in range(10):
            start = (len(candidates) * stratum) // 10
            stop = (len(candidates) * (stratum + 1)) // 10
            values = sorted(
                candidates[start:stop],
                key=lambda item: (
                    len("".join(str(value) for value in item["raw_fragments"])),
                    len(item["candidate_ids"]),
                    str(item["assembly_id"]),
                ),
            )
            index = round((len(values) - 1) * QUANTILES[stratum])
            selected.append(values[index])
    return selected


def build_plan(processor: Pix2TexCliEquationRecognizer) -> dict[str, object]:
    proposed = json.loads(
        exact(ROOT / "proposed-primary-recognition-inventory.json")
    )
    selected = select_canary(proposed["items"])
    items = []
    for sequence, value in enumerate(selected, 1):
        image = exact(ROOT / value["rendered_member"])
        if (
            len(image) != value["rendered_bytes"]
            or digest(image) != value["rendered_sha256"]
        ):
            raise RuntimeError(f"canary image differs: {value['assembly_id']}")
        items.append(
            {
                "sequence": sequence,
                "book": value["book"],
                "chunk_number": value["chunk_number"],
                "page_index": value["page_index"],
                "assembly_id": value["assembly_id"],
                "candidate_ids": value["candidate_ids"],
                "raw_fragments": value["raw_fragments"],
                "sanitized_native_text": value["sanitized_native_text"],
                "rendered_member": value["rendered_member"],
                "rendered_sha256": value["rendered_sha256"],
                "rendered_bytes": value["rendered_bytes"],
            }
        )
    body = {
        "contract_version": "1.0",
        "scope": "thirty-item-local-pix2tex-canary",
        "selection_policy": "ten_equal_order_strata_per_book_with_fixed_feature_quantiles",
        "selection_quantiles": list(QUANTILES),
        "processor_identity": CanonicalJsonSerializer.project_object(
            processor.identity
        ),
        "item_count": len(items),
        "items": items,
        "authorization": {
            "local_pix2tex_model_execution": True,
            "maximum_invocations": 30,
            "assemblies_per_invocation": 1,
            "external_network": False,
            "ollama": False,
            "live_database": False,
            "search_indexing": False,
            "publication": False,
        },
        "result_policy": [
            "automated",
            "unreviewed",
            "unaccepted",
            "chunk_text_ineligible",
        ],
    }
    return {
        **body,
        "canary_plan_id": identity(
            "reference-multimodal-pix2tex-canary-plan", body
        ),
    }


def single_assembly_result(
    full: EquationAssemblyResult, assembly: object
) -> EquationAssemblyResult:
    artifact_id = stable_id(
        "equation-assembly-artifact",
        EQUATION_ASSEMBLY_CONTRACT_VERSION,
        full.source_id,
        full.source_content_hash,
        full.document_id,
        full.detection_result_id,
        (assembly.assembly_id,),
    )
    return EquationAssemblyResult(
        artifact_id=artifact_id,
        source_id=full.source_id,
        source_content_hash=full.source_content_hash,
        document_id=full.document_id,
        detection_result_id=full.detection_result_id,
        assemblies=(assembly,),
    )


def main() -> None:
    processor = recognizer()
    plan = build_plan(processor)
    plan_status = json_once(CANARY_ROOT / "plan.json", plan)
    authoritative_plan = json.loads(exact(CANARY_ROOT / "plan.json"))
    if authoritative_plan != plan:
        raise RuntimeError("authoritative canary plan differs")
    preparation_plan = json.loads(exact(ROOT / "plan.json"))
    books = {book["book"]: book for book in preparation_plan["books"]}
    quality_module = runpy.run_path(str(QUALITY_SCRIPT))
    analyze = quality_module["analyze"]
    source_cache: dict[str, bytes] = {}
    assembly_cache: dict[tuple[str, int], dict[str, object]] = {}
    results = []
    for item in plan["items"]:
        sequence = int(item["sequence"])
        result_path = CANARY_ROOT / "results" / f"result-{sequence:03d}.json"
        if result_path.exists():
            result_bytes = exact(result_path)
            results.append(
                {
                    "sequence": sequence,
                    "status": "unchanged",
                    "path": str(result_path.relative_to(CANARY_ROOT)),
                    "sha256": digest(result_bytes),
                    "bytes": len(result_bytes),
                    "result": json.loads(result_bytes),
                }
            )
            continue
        book_name = str(item["book"])
        book = books[book_name]
        source = source_cache.setdefault(
            book_name,
            exact(REFERENCES / book["source_sha256"] / "document.pdf"),
        )
        key = (book_name, int(item["chunk_number"]))
        if key not in assembly_cache:
            chunk = next(
                value
                for value in book["chunks"]
                if value["chunk_number"] == key[1]
            )
            _equations, _figures, _tables, full = analyze(book, chunk, source)
            assembly_cache[key] = {
                value.assembly_id: value for value in full.assemblies
            }
            assembly_cache[key]["__full__"] = full
        assemblies = assembly_cache[key]
        assembly = assemblies.get(item["assembly_id"])
        full = assemblies["__full__"]
        if assembly is None:
            raise RuntimeError(
                f"planned assembly unavailable: {item['assembly_id']}"
            )
        if digest(assembly.rendered_region.content) != item["rendered_sha256"]:
            raise RuntimeError(
                f"planned assembly image differs: {item['assembly_id']}"
            )
        artifact = single_assembly_result(full, assembly)
        request = EquationRecognitionRequest.create(
            assembly_artifact=artifact, processor_identity=processor.identity
        )
        started = time.monotonic()
        recognition = processor.action(request=request)
        elapsed = time.monotonic() - started
        value = {
            "contract_version": "1.0",
            "canary_plan_id": plan["canary_plan_id"],
            "sequence": sequence,
            "book": book_name,
            "chunk_number": item["chunk_number"],
            "page_index": item["page_index"],
            "assembly_id": item["assembly_id"],
            "request_id": request.request_id,
            "recognition": CanonicalJsonSerializer.project_object(recognition),
            "automated": True,
            "reviewed": False,
            "accepted": False,
            "chunk_text_eligible": False,
        }
        content = (
            json.dumps(
                value, ensure_ascii=False, indent=2, sort_keys=True
            ).encode()
            + b"\n"
        )
        create_once(result_path, content)
        results.append(
            {
                "sequence": sequence,
                "status": "created",
                "path": str(result_path.relative_to(CANARY_ROOT)),
                "sha256": digest(content),
                "bytes": len(content),
                "elapsed_seconds": round(elapsed, 3),
                "result": value,
            }
        )
        proposal = recognition.proposals[0]
        print(
            f"{sequence:02d}/30 {book_name} page={item['page_index']} status={proposal.status.value} exit={recognition.invocation_exit_code} elapsed={elapsed:.1f}s",
            flush=True,
        )
    records = [
        {key: result[key] for key in ("sequence", "path", "sha256", "bytes")}
        | {
            "book": result["result"]["book"],
            "assembly_id": result["result"]["assembly_id"],
            "request_id": result["result"]["request_id"],
            "artifact_id": result["result"]["recognition"]["artifact_id"],
            "invocation_exit_code": result["result"]["recognition"][
                "invocation_exit_code"
            ],
            "proposal_status": result["result"]["recognition"]["proposals"][0][
                "status"
            ],
        }
        for result in results
    ]
    body = {
        "contract_version": "1.0",
        "canary_plan_id": plan["canary_plan_id"],
        "processor_identity_digest": processor.identity.identity_digest,
        "result_count": len(records),
        "proposed_count": sum(
            item["proposal_status"] == "proposed" for item in records
        ),
        "failed_count": sum(
            item["proposal_status"] == "failed" for item in records
        ),
        "not_requested_count": sum(
            item["proposal_status"] == "not_requested" for item in records
        ),
        "nonzero_exit_count": sum(
            item["invocation_exit_code"] != 0 for item in records
        ),
        "records": records,
        "limitations": [
            "automated_unreviewed",
            "unaccepted",
            "chunk_text_ineligible",
            "canary_only",
        ],
    }
    inventory = {
        **body,
        "canary_inventory_id": identity(
            "reference-multimodal-pix2tex-canary-inventory", body
        ),
    }
    inventory_status = json_once(CANARY_ROOT / "inventory.json", inventory)
    print(
        json.dumps(
            {
                "plan_status": plan_status,
                "inventory_status": inventory_status,
                "canary_plan_id": plan["canary_plan_id"],
                "canary_inventory_id": inventory["canary_inventory_id"],
                "plan_sha256": digest(exact(CANARY_ROOT / "plan.json")),
                "inventory_sha256": digest(
                    exact(CANARY_ROOT / "inventory.json")
                ),
                "result_count": inventory["result_count"],
                "proposed_count": inventory["proposed_count"],
                "failed_count": inventory["failed_count"],
                "not_requested_count": inventory["not_requested_count"],
                "nonzero_exit_count": inventory["nonzero_exit_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
