#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from projectkoios.ingestion.page_projection import (
    PageProjectionPlanEntry,
    page_projection_validation_report_bytes,
    validate_page_projection,
)

ARTIFACT_ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-multimodal-v1"
)
REFERENCE_ROOT = Path("/Users/eugene/projects/projectkoios/references")
TEXT_ROOT = Path(
    "/Users/eugene/projects/projectkoios/artifacts/reference-page-resolution-v1/objects"
)


@dataclass(frozen=True)
class Book:
    document_id: str
    name: str
    filename: str
    title: str
    digest: str
    pages: int

    @property
    def root(self) -> Path:
        return ARTIFACT_ROOT / self.name

    @property
    def source(self) -> Path:
        return REFERENCE_ROOT / self.digest / "document.pdf"

    @property
    def baseline(self) -> Path:
        return (
            TEXT_ROOT
            / self.digest[:2]
            / self.digest
            / "composed-transcript.json"
        )


BOOKS = (
    Book(
        "doc-01",
        "Kittel8ed",
        "Kittel8ed.pdf",
        "Introduction to Solid State Physics",
        "7c177d8ce281eeb1a1e0897e8d711bd908c2657ec42abd690ff1105533b7a6ed",
        700,
    ),
    Book(
        "doc-02",
        "SimonSS1Ed",
        "SimonSS1Ed.pdf",
        "The Oxford Solid State Basics",
        "46807198536b8672000463b8d9c8ae555f4955ba0ad0e80cec19b01671030be2",
        305,
    ),
    Book(
        "doc-03",
        "AshcroftMermin_SolidStatePhysics",
        "AshcroftMermin_SolidStatePhysics.pdf",
        "Solid State Physics",
        "6299153bde8e4ee49583ca8abfcc9afd687a34c25a0d06252681200fbda781ad",
        848,
    ),
    Book(
        "doc-04",
        "Marder2Ed",
        "Marder2Ed.pdf",
        "Condensed Matter Physics",
        "bc1ce37437da489aa1b35b5fe86750cf3bd35a9c0c9df7597b1e55871a243d93",
        985,
    ),
    Book(
        "doc-05",
        "SzeNg3Ed",
        "SzeNg3Ed.pdf",
        "Physics of Semiconductor Devices",
        "7909c81fe5c12006dbaf4f664b029b67319bd7c45fe86d97ccedaf229067a221",
        763,
    ),
    Book(
        "doc-06",
        "Neaman3Ed",
        "Neaman3Ed.pdf",
        "Semiconductor Physics and Devices",
        "31dce1ae5f09199951a496da12d00f7873f0ccbce00f3cd67449438b187d3761",
        566,
    ),
    Book(
        "doc-07",
        "SzeLee3Ed",
        "SzeLee3Ed.pdf",
        "Semiconductor Devices: Physics and Technology",
        "539257eb20229bee438dbd628e017bcf8ba6bb6348198ce1e9000cd685d7263e",
        590,
    ),
    Book(
        "doc-08",
        "YuCardona4Ed",
        "YuCardona4Ed.pdf",
        "Fundamentals of Semiconductors",
        "acfc317504ba1e20a14686c9cbf66b542fb844b4d29b9cc66307598961963f30",
        793,
    ),
    Book(
        "doc-09",
        "RudanPhysicsSemiconductors",
        "RudanPhysicsSemiconductors.pdf",
        "Physics of Semiconductor Devices",
        "53960e40556225a3b56cbd601409d737eb0f8384026550dce0bc16ef7aca7014",
        648,
    ),
)


def atomic_bytes(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def validate(book: Book) -> dict[str, object]:
    plan = PageProjectionPlanEntry(
        document_id=book.document_id,
        filename=book.filename,
        title=book.title,
        source_sha256=book.digest,
        expected_page_count=book.pages,
    )
    projection = validate_page_projection(
        plan,
        source_path=book.source,
        transcript_path=book.root / "reading-transcript.jsonl",
        summary_path=book.root / "reading-transcript-summary.json",
        baseline_path=book.baseline,
        media_root=book.root,
    )
    atomic_bytes(
        book.root / "reading-transcript-validation.json",
        page_projection_validation_report_bytes(projection.report),
    )
    return asdict(projection.report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("books", nargs="*")
    arguments = parser.parse_args()
    requested = set(arguments.books)
    selected = tuple(
        book
        for book in BOOKS
        if not requested
        or book.name in requested
        or book.document_id in requested
    )
    if requested and len(selected) != len(requested):
        raise ValueError("unknown or duplicate book selector")
    reports = [
        validate(book)
        for book in selected
        if (book.root / "reading-transcript.jsonl").is_file()
    ]
    print(json.dumps(reports, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
