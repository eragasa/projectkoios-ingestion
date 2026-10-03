from __future__ import annotations

import argparse
import json
import re
import stat
from pathlib import Path

from projectkoios.ingestion.cli import (
    ExtractionCacheOperationError,
    extract_pdf_evidence,
)
from projectkoios.ingestion.integrations.disk.extraction.store import (
    DiskExtractionPublicationStore,
)
from projectkoios.ingestion.integrations.mongodb.extraction.store import (
    MongoExtractionPublicationStore,
)
from projectkoios.ingestion.pdf import DEFAULT_MAXIMUM_PDF_PAGES
from projectkoios.ingestion.storage.extraction.error import (
    ExtractionPublicationError,
)
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)
from pymongo.errors import PyMongoError

from scripts.mongodb_extraction_connection import (
    MongoExtractionConnectionMetadata,
    open_mongo_extraction_client,
)

_SHA256 = re.compile(r"[0-9a-f]{64}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.extraction_publication",
        description=(
            "Publish one exact PDF extraction to the authoritative disk "
            "journal and its MongoDB projection. The command is a dry run "
            "unless --apply is supplied."
        ),
    )
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--expected-source-byte-size", type=int, required=True)
    parser.add_argument("--connection", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--locator")
    parser.add_argument("--low-text-threshold", type=int, default=40)
    parser.add_argument(
        "--maximum-pages",
        type=int,
        default=DEFAULT_MAXIMUM_PDF_PAGES,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="extract and durably publish the exact source",
    )
    return parser


def _validate_source_plan(
    path: Path,
    *,
    expected_sha256: str,
    expected_byte_size: int,
) -> Path:
    if not _SHA256.fullmatch(expected_sha256):
        raise ValueError("expected source hash must be lowercase SHA-256")
    if expected_byte_size <= 0:
        raise ValueError("expected source byte size must be positive")
    source = path.expanduser().absolute()
    if source.resolve() != source:
        raise ValueError("PDF source cannot traverse a symlink")
    metadata = source.lstat()
    if not stat.S_ISREG(metadata.st_mode) or source.is_symlink():
        raise ValueError("PDF source must be a safe regular file")
    if metadata.st_size != expected_byte_size:
        raise ValueError("PDF source size does not match the plan")
    return source


def main() -> None:
    parser = _parser()
    arguments = parser.parse_args()
    try:
        metadata = MongoExtractionConnectionMetadata.load(
            arguments.connection
        )
        source = _validate_source_plan(
            arguments.pdf,
            expected_sha256=arguments.expected_source_sha256,
            expected_byte_size=arguments.expected_source_byte_size,
        )
        if not arguments.source_id.strip():
            raise ValueError("source ID must be nonempty")
        if not arguments.apply:
            print(
                json.dumps(
                    {
                        "apply": False,
                        "database": metadata.database,
                        "expected_source_byte_size": (
                            arguments.expected_source_byte_size
                        ),
                        "expected_source_sha256": (
                            arguments.expected_source_sha256
                        ),
                        "pdf": str(source),
                        "recovery_root": str(metadata.recovery_root),
                        "source_id": arguments.source_id,
                    },
                    sort_keys=True,
                )
            )
            return
        _, extraction = extract_pdf_evidence(
            source,
            source_id=arguments.source_id,
            cache_root=arguments.cache_root,
            locator=arguments.locator,
            low_text_threshold=arguments.low_text_threshold,
            expected_source_sha256=arguments.expected_source_sha256,
            expected_source_byte_size=arguments.expected_source_byte_size,
            maximum_pages=arguments.maximum_pages,
        )
        request = ExtractionPublicationRequest.create(
            extraction=extraction,
        )
        with open_mongo_extraction_client(metadata) as client:
            journal = DiskExtractionPublicationStore(metadata.recovery_root)
            store = MongoExtractionPublicationStore(
                database=client[metadata.database],
                journal=journal,
            )
            result = store.publish(request=request)
        print(
            json.dumps(
                {
                    "apply": True,
                    "block_count": sum(
                        len(page.blocks)
                        for page in extraction.document.pages
                    ),
                    "database": metadata.database,
                    "document_id": result.document_id,
                    "journal_sequence": result.journal_sequence,
                    "manifest_id": extraction.manifest.manifest_id,
                    "page_count": len(extraction.document.pages),
                    "payload_byte_size": result.payload_byte_size,
                    "payload_sha256": result.payload_sha256,
                    "replayed": result.replayed,
                    "request_id": result.request_id,
                },
                sort_keys=True,
            )
        )
    except (
        ExtractionCacheOperationError,
        ExtractionPublicationError,
        OSError,
        PyMongoError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
