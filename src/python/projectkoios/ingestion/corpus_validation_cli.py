from __future__ import annotations

import argparse
import json
from pathlib import Path

from projectkoios.ingestion.corpus import (
    PdfCorpusLimits,
    load_pdf_corpus_plans,
    validate_pdf_corpus,
)
from projectkoios.ingestion.pdf import PdfExtractionConfiguration

_DEFAULT_LIMITS = PdfCorpusLimits()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="koios-validate-pdf-corpus")
    parser.add_argument("--plans", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--low-text-threshold", type=int, default=40)
    parser.add_argument("--maximum-pages", type=int, default=10_000)
    parser.add_argument(
        "--max-files", type=int, default=_DEFAULT_LIMITS.max_files
    )
    parser.add_argument(
        "--max-source-bytes",
        type=int,
        default=_DEFAULT_LIMITS.max_file_bytes,
    )
    parser.add_argument(
        "--max-total-bytes",
        type=int,
        default=_DEFAULT_LIMITS.max_total_bytes,
    )
    return parser


def main(arguments: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(arguments)
    try:
        limits = PdfCorpusLimits(
            max_files=args.max_files,
            max_file_bytes=args.max_source_bytes,
            max_total_bytes=args.max_total_bytes,
        )
        plans = load_pdf_corpus_plans(args.plans, limits=limits)
        summary = validate_pdf_corpus(
            plans,
            source_root=args.source_root,
            output_root=args.output_root,
            configuration=PdfExtractionConfiguration(
                low_text_character_threshold=args.low_text_threshold,
                maximum_pages=args.maximum_pages,
            ),
            limits=limits,
        )
    except (OSError, TypeError, ValueError) as error:
        parser.error(f"corpus validation failed: {error}")
    print(
        json.dumps(
            {
                "document_count": summary.document_count,
                "documents_requiring_ocr": (summary.documents_requiring_ocr),
                "empty_page_count": summary.empty_page_count,
                "limitations": [
                    "native_text_only",
                    "automated_unreviewed",
                    "ocr_not_executed",
                    "equation_transcription_not_executed",
                    "embeddings_not_generated",
                    "index_not_generated",
                    "not_rag_ready",
                ],
                "low_text_page_count": summary.low_text_page_count,
                "native_text_utf8_bytes": summary.native_text_utf8_bytes,
                "page_count": summary.page_count,
                "source_bytes": summary.source_bytes,
                "status": "valid",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
