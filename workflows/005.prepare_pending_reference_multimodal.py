#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import stat
from pathlib import Path

REFERENCE_ROOT = Path("/Users/eugene/projects/projectkoios/references")
RESOLUTION_ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-page-resolution-v1/objects"
)
OUTPUT_ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-preparation-v2"
)
CHUNK_PAGES = 10
BOOKS = (
    (
        "SzeLee3Ed",
        "539257eb20229bee438dbd628e017bcf8ba6bb6348198ce1e9000cd685d7263e",
        590,
    ),
    (
        "YuCardona4Ed",
        "acfc317504ba1e20a14686c9cbf66b542fb844b4d29b9cc66307598961963f30",
        793,
    ),
    (
        "RudanPhysicsSemiconductors",
        "53960e40556225a3b56cbd601409d737eb0f8384026550dce0bc16ef7aca7014",
        648,
    ),
)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def identified(namespace: str, value: object) -> str:
    return f"{namespace}:sha256:{sha256(canonical(value))}"


def exact_file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"missing or unsafe file: {path}")
    return path.read_bytes()


def validate_text_page(
    page: dict[str, object], index: int, physical: bool
) -> int:
    expected = index + 1 if physical else index
    key = "physical_page_number" if physical else "page_index"
    if page.get(key) != expected:
        raise RuntimeError(f"{key} coverage differs at {index}")
    text = page.get("text")
    if not isinstance(text, str):
        raise RuntimeError(f"page {index} text is not a string")
    payload = text.encode()
    if page.get("text_utf8_byte_length") != len(payload):
        raise RuntimeError(f"page {index} text byte count differs")
    if page.get("text_sha256") != sha256(payload):
        raise RuntimeError(f"page {index} text digest differs")
    return len(payload)


def validate_book(name: str, digest: str, pages: int) -> dict[str, object]:
    reference = REFERENCE_ROOT / digest
    source_path = reference / "document.pdf"
    source = exact_file(source_path)
    if sha256(source) != digest:
        raise RuntimeError(f"{name}: source digest differs")
    if stat.S_IMODE(source_path.stat().st_mode) & 0o077:
        raise RuntimeError(f"{name}: source permissions are not private")

    native_path = reference / "transcript.json"
    native_bytes = exact_file(native_path)
    native = json.loads(native_bytes)
    native_pages = native.get("pages")
    if (
        native.get("page_count") != pages
        or not isinstance(native_pages, list)
        or len(native_pages) != pages
    ):
        raise RuntimeError(f"{name}: native page coverage differs")
    native_text_bytes = sum(
        validate_text_page(page, index, True)
        for index, page in enumerate(native_pages)
    )

    object_root = RESOLUTION_ROOT / digest[:2] / digest
    composed_path = object_root / "composed-transcript.json"
    composed_bytes = exact_file(composed_path)
    composed = json.loads(composed_bytes)
    composed_pages = composed.get("pages")
    if (
        composed.get("complete") is not True
        or composed.get("page_count") != pages
        or not isinstance(composed_pages, list)
        or len(composed_pages) != pages
    ):
        raise RuntimeError(f"{name}: composed page coverage differs")
    composed_text_bytes = 0
    source_counts: dict[str, int] = {}
    for index, page in enumerate(composed_pages):
        composed_text_bytes += validate_text_page(page, index, False)
        if page.get("page_id") != native_pages[index].get("page_id"):
            raise RuntimeError(
                f"{name}: composed/native page identity differs at {index}"
            )
        chosen = page.get("chosen_source")
        if chosen not in {"native", "ocr", "ollama"}:
            raise RuntimeError(f"{name}: unsupported chosen source at {index}")
        source_counts[chosen] = source_counts.get(chosen, 0) + 1

    ocr_records: list[dict[str, object]] = []
    pages_root = object_root / "pages"
    ocr_paths = (
        tuple(sorted(pages_root.glob("page-*/ocr.json")))
        if pages_root.is_dir()
        else ()
    )
    for path in ocr_paths:
        physical_page = int(path.parent.name.removeprefix("page-"))
        index = physical_page - 1
        if not 0 <= index < pages:
            raise RuntimeError(f"{name}: OCR page path is outside coverage")
        payload = exact_file(path)
        value = json.loads(payload)
        if (
            value.get("contract_version") != "1.0"
            or value.get("status") != "completed"
        ):
            raise RuntimeError(
                f"{name}: OCR result is not completed at page {physical_page}"
            )
        selections = value.get("selection_results")
        request_selections = value.get("request", {}).get("selections")
        if (
            not isinstance(selections, list)
            or len(selections) != 1
            or not isinstance(request_selections, list)
            or len(request_selections) != 1
        ):
            raise RuntimeError(
                f"{name}: OCR result does not cover exactly one page"
            )
        rendered = (
            request_selections[0].get("image", {}).get("rendered_region", {})
        )
        if (
            rendered.get("source_content_hash") != digest
            or rendered.get("page_index") != index
        ):
            raise RuntimeError(
                f"{name}: OCR source binding differs at page {physical_page}"
            )
        encoded = rendered.get("content")
        if isinstance(encoded, dict) and isinstance(encoded.get("hex"), str):
            image = bytes.fromhex(encoded["hex"])
        elif isinstance(encoded, str):
            image = base64.b64decode(encoded, validate=True)
        else:
            raise RuntimeError(f"{name}: OCR rendered content is unavailable")
        if len(image) != rendered.get("byte_length") or sha256(
            image
        ) != rendered.get("content_sha256"):
            raise RuntimeError(
                f"{name}: OCR rendered bytes differ at page {physical_page}"
            )
        ocr_records.append(
            {
                "physical_page_number": physical_page,
                "page_index": index,
                "ocr_result_id": value.get("result_id"),
                "ocr_cache_key": value.get("cache_key"),
                "artifact_sha256": sha256(payload),
                "artifact_bytes": len(payload),
                "rendered_image_sha256": rendered.get("content_sha256"),
                "rendered_image_bytes": len(image),
                "chosen_source": composed_pages[index].get("chosen_source"),
            }
        )

    chunks = []
    for number in range(1, math.ceil(pages / CHUNK_PAGES) + 1):
        first = (number - 1) * CHUNK_PAGES
        last = min(pages, first + CHUNK_PAGES)
        chunk = {
            "chunk_number": number,
            "first_page_index": first,
            "last_page_index_exclusive": last,
            "page_count": last - first,
            "planned_operations": [
                "extract",
                "layout",
                "equation-detect",
                "figure-detect",
                "table-detect",
                "render-candidates",
            ],
        }
        chunks.append(
            {
                **chunk,
                "chunk_plan_id": identified(
                    "reference-multimodal-chunk-plan", chunk
                ),
            }
        )

    evidence = {
        "book": name,
        "source_sha256": digest,
        "source_bytes": len(source),
        "page_count": pages,
        "native_transcript_sha256": sha256(native_bytes),
        "native_text_utf8_bytes": native_text_bytes,
        "native_empty_pages": native.get("empty_page_count"),
        "composed_transcript_sha256": sha256(composed_bytes),
        "composed_transcript_id": composed.get("composed_transcript_id"),
        "composed_text_utf8_bytes": composed_text_bytes,
        "chosen_source_counts": dict(sorted(source_counts.items())),
        "ocr_artifact_count": len(ocr_records),
        "ocr_artifact_bytes": sum(
            int(item["artifact_bytes"]) for item in ocr_records
        ),
        "ocr_rendered_image_bytes": sum(
            int(item["rendered_image_bytes"]) for item in ocr_records
        ),
        "ocr_records": ocr_records,
        "chunks": chunks,
    }
    return {
        **evidence,
        "book_plan_id": identified("reference-multimodal-book-plan", evidence),
    }


def create_once(path: Path, content: bytes) -> str:
    if path.exists():
        if (
            path.is_symlink()
            or not path.is_file()
            or path.read_bytes() != content
        ):
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


def main() -> None:
    books = [validate_book(*book) for book in BOOKS]
    plan_body = {
        "contract_version": "1.0",
        "chunk_pages": CHUNK_PAGES,
        "authorization": "deterministic-local-preparation-only",
        "prohibited_operations": [
            "model-execution",
            "external-network-processing",
            "live-database",
            "search-indexing",
            "publication",
        ],
        "books": books,
    }
    plan = {
        **plan_body,
        "plan_id": identified(
            "reference-multimodal-preparation-plan", plan_body
        ),
    }
    content = (
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )
    status = create_once(OUTPUT_ROOT / "plan.json", content)
    print(
        json.dumps(
            {
                "status": status,
                "plan_id": plan["plan_id"],
                "plan_sha256": sha256(content),
                "book_count": len(books),
                "page_count": sum(int(book["page_count"]) for book in books),
                "chunk_count": sum(len(book["chunks"]) for book in books),
                "ocr_artifact_count": sum(
                    int(book["ocr_artifact_count"]) for book in books
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
