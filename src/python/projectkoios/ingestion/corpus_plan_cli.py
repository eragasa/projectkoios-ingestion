from __future__ import annotations

import argparse
import json
from pathlib import Path

from projectkoios.ingestion.corpus import (
    PdfCorpusLimits,
    PdfCorpusPublicationError,
    prepare_pdf_corpus,
    publish_pdf_corpus_plans,
)

_DEFAULT_LIMITS = PdfCorpusLimits()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="koios-plan-pdf-corpus")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--max-files", type=int, default=_DEFAULT_LIMITS.max_files
    )
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=_DEFAULT_LIMITS.max_file_bytes,
    )
    parser.add_argument(
        "--max-total-bytes",
        type=int,
        default=_DEFAULT_LIMITS.max_total_bytes,
    )
    parser.add_argument(
        "--batch-size", type=int, default=_DEFAULT_LIMITS.batch_size
    )
    parser.add_argument("--apply", action="store_true")
    return parser


def main(arguments: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(arguments)
    try:
        limits = PdfCorpusLimits(
            max_files=args.max_files,
            max_file_bytes=args.max_file_bytes,
            max_total_bytes=args.max_total_bytes,
            batch_size=args.batch_size,
        )
        prepared = prepare_pdf_corpus(
            args.source_root,
            limits=limits,
        )
    except (OSError, ValueError) as error:
        parser.error(f"corpus planning failed: {error}")

    summary: dict[str, object] = {
        "discovered_file_count": prepared.discovered_file_count,
        "duplicate_file_count": prepared.duplicate_file_count,
        "plan_count": len(prepared.plans),
        "status": "planned",
        "total_source_bytes": prepared.total_source_bytes,
        "unique_file_count": prepared.unique_file_count,
    }
    if not args.apply:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 2
    try:
        action = publish_pdf_corpus_plans(
            args.output,
            prepared.plans,
            limits=limits,
        )
    except (OSError, PdfCorpusPublicationError, ValueError) as error:
        parser.error(f"corpus plan publication failed: {error}")
    summary["action"] = action
    summary["status"] = "completed"
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
