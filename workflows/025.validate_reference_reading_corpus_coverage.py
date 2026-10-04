#!/Users/eugene/repos/projectkoios-ingestion/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

ARTIFACTS = Path("/Users/eugene/projects/projectkoios/artifacts")
ROOT = ARTIFACTS / "reference-reading-corpus-coverage-v2"
PNG = b"\x89PNG\r\n\x1a\n"


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def identity(namespace: str, value: object) -> str:
    return f"{namespace}:sha256:{digest(canonical(value))}"


def exact(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"missing or unsafe file: {path}")
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise RuntimeError(f"file permissions differ: {path}")
    return path.read_bytes()


def create_once(path: Path, content: bytes) -> str:
    if path.exists():
        if exact(path) != content:
            raise RuntimeError(f"create-once artifact differs: {path}")
        return "unchanged"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return "created"


def validate_media(root: Path, value: dict[str, object]) -> None:
    relative = value["png_path"]
    path = root / relative
    content = exact(path)
    if not content.startswith(PNG):
        raise RuntimeError(f"media is not PNG: {path}")
    expected = value.get("png_sha256")
    if expected is not None and digest(content) != expected:
        raise RuntimeError(f"media digest differs: {path}")


def main() -> None:
    for directory in [
        ROOT,
        *[path for path in ROOT.rglob("*") if path.is_dir()],
    ]:
        if (
            directory.is_symlink()
            or stat.S_IMODE(directory.stat().st_mode) != 0o700
        ):
            raise RuntimeError(f"directory permissions differ: {directory}")
    coverage_bytes = exact(ROOT / "coverage.json")
    coverage = json.loads(coverage_bytes)
    coverage_id = coverage.pop("coverage_inventory_id")
    if coverage_id != identity("reference-reading-corpus-coverage", coverage):
        raise RuntimeError("coverage identity differs")
    coverage["coverage_inventory_id"] = coverage_id

    equation_ids: set[str] = set()
    page_count = 0
    equation_count = 0
    figure_count = 0
    table_count = 0
    explicit_unreviewed = 0
    inferred_unreviewed = 0
    media_paths: set[tuple[str, str]] = set()
    for record in coverage["documents"]:
        root = Path(record["artifact_root"])
        if root.is_symlink() or not root.is_dir():
            raise RuntimeError(f"artifact root is unsafe: {root}")
        transcript = exact(root / "reading-transcript.jsonl")
        if digest(transcript) != record["transcript_sha256"]:
            raise RuntimeError(f"{record['book']}: transcript digest differs")
        lines = transcript.splitlines()
        if len(lines) != record["page_count"]:
            raise RuntimeError(f"{record['book']}: page coverage differs")
        document_equations = 0
        document_figures: set[str] = set()
        document_tables: set[str] = set()
        for index, line in enumerate(lines):
            page = json.loads(line)
            if record["document_id"] <= "doc-06":
                if page["physical_page"] != index + 1:
                    raise RuntimeError(
                        f"{record['book']}: physical page order differs"
                    )
                values = page["blocks"]
                for value in values:
                    kind = value["type"]
                    if kind == "equation":
                        equation_id = value["assembly_id"]
                        if equation_id in equation_ids:
                            raise RuntimeError(
                                "equation identity is duplicated"
                            )
                        equation_ids.add(equation_id)
                        document_equations += 1
                        if (
                            value["latex"] is not None
                            or value["mathml"] is not None
                        ):
                            raise RuntimeError(
                                "recognized equation text remains"
                            )
                        if (
                            value["accepted"] is not False
                            or value["review_required"] is not True
                            or value["chunk_text_eligible"] is not False
                            or value["review_status"] != "unreviewed"
                        ):
                            raise RuntimeError("equation review gate differs")
                        explicit_unreviewed += 1
                        validate_media(root, value)
                        media_paths.add((str(root), value["png_path"]))
                    elif kind == "figure":
                        document_figures.add(
                            value.get("candidate_id", value["png_path"])
                        )
                        validate_media(root, value)
                        media_paths.add((str(root), value["png_path"]))
            else:
                if (
                    page["page_index"] != index
                    or page["physical_page"] != index + 1
                ):
                    raise RuntimeError(
                        f"{record['book']}: physical page order differs"
                    )
                for value in page["visual_evidence"]:
                    kind = value["evidence_type"]
                    if kind == "equation":
                        equation_id = value["assembly_id"]
                        if equation_id in equation_ids:
                            raise RuntimeError(
                                "equation identity is duplicated"
                            )
                        equation_ids.add(equation_id)
                        document_equations += 1
                        if (
                            value["recognized_latex"] is not None
                            or value["recognized_mathml"] is not None
                        ):
                            raise RuntimeError(
                                "recognized equation text remains"
                            )
                        if (
                            value["accepted"] is not False
                            or value["review_required"] is not True
                            or value["chunk_text_eligible"] is not False
                            or value["recognition_status"]
                            != "not_requested_processor_unsuitable"
                        ):
                            raise RuntimeError("equation review gate differs")
                        inferred_unreviewed += 1
                    elif kind == "figure":
                        document_figures.add(value["candidate_id"])
                    elif kind == "table":
                        document_tables.add(value["candidate_id"])
                    for rendered in value["rendered_members"]:
                        path = (
                            ARTIFACTS
                            / "reference-multimodal-preparation-v2"
                            / rendered["path"]
                        )
                        content = exact(path)
                        if (
                            len(content) != rendered["bytes"]
                            or digest(content) != rendered["sha256"]
                        ):
                            raise RuntimeError(
                                f"rendered evidence differs: {path}"
                            )
                        media_paths.add((str(path.parent), path.name))
        if document_equations != record["equation_evidence_count"]:
            raise RuntimeError(f"{record['book']}: equation count differs")
        if len(document_figures) != record["figure_evidence_count"]:
            raise RuntimeError(f"{record['book']}: figure count differs")
        if len(document_tables) != record.get("table_evidence_count", 0):
            raise RuntimeError(f"{record['book']}: table count differs")
        page_count += len(lines)
        equation_count += document_equations
        figure_count += len(document_figures)
        table_count += len(document_tables)

    if (
        page_count != coverage["page_count"]
        or equation_count != coverage["equation_evidence_count"]
        or figure_count != coverage["figure_evidence_count"]
        or table_count != coverage["table_evidence_count"]
        or len(equation_ids) != equation_count
    ):
        raise RuntimeError("coverage totals differ")
    if explicit_unreviewed + inferred_unreviewed != equation_count:
        raise RuntimeError("equation review-status coverage differs")
    body = {
        "contract_version": "1.0",
        "status": "valid",
        "coverage_inventory_id": coverage_id,
        "coverage_sha256": digest(coverage_bytes),
        "document_count": coverage["document_count"],
        "page_count": page_count,
        "equation_evidence_count": equation_count,
        "figure_evidence_count": figure_count,
        "table_evidence_count": table_count,
        "recognized_equation_text_count": 0,
        "accepted_equation_count": 0,
        "review_required_equation_count": equation_count,
        "chunk_text_eligible_equation_count": 0,
        "explicit_unreviewed_equation_count": explicit_unreviewed,
        "not_requested_unreviewed_equation_count": inferred_unreviewed,
        "unique_equation_identity_count": len(equation_ids),
        "referenced_media_count": len(media_paths),
    }
    value = {
        **body,
        "validation_id": identity(
            "reference-reading-corpus-coverage-validation", body
        ),
    }
    content = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )
    status = create_once(ROOT / "validation.json", content)
    print(
        json.dumps(
            {
                "status": status,
                "validation_id": value["validation_id"],
                "validation_sha256": digest(content),
                "coverage_inventory_id": coverage_id,
                "document_count": value["document_count"],
                "page_count": page_count,
                "equation_evidence_count": equation_count,
                "figure_evidence_count": figure_count,
                "table_evidence_count": table_count,
                "recognized_equation_text_count": 0,
                "referenced_media_count": len(media_paths),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    os.umask(0o077)
    main()
