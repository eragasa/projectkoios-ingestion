from __future__ import annotations

import argparse
import json
from pathlib import Path

from projectkoios.ingestion.batch import PdfBatchPlan
from projectkoios.ingestion.transcript_v2_batch import (
    TranscriptV2BatchPublicationError,
    build_transcript_v2_batch_plan,
    publish_durable_plan,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="koios-plan-pdf-transcripts-v2-batch"
    )
    parser.add_argument("source_plan", type=Path)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--ingestion-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--low-text-threshold", type=int, default=40)
    parser.add_argument("--apply", action="store_true")
    return parser


def main(arguments: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(arguments)
    try:
        if args.source_plan.is_symlink() or not args.source_plan.is_file():
            raise ValueError("source plan must be a safe regular file")
        source_plan = PdfBatchPlan.from_json(
            args.source_plan.read_text(encoding="utf-8")
        )
        plan = build_transcript_v2_batch_plan(
            source_plan,
            source_root=args.source_root,
            ingestion_root=args.ingestion_root,
            extraction_low_text_threshold=args.low_text_threshold,
        )
    except (OSError, ValueError) as error:
        parser.error(f"invalid transcript-v2 planning input: {error}")
    summary = {
        "artifact_generation": plan.artifact_generation,
        "item_count": len(plan.items),
        "output": args.output.as_posix(),
        "plan_id": plan.plan_id,
        "status": "planned",
    }
    if not args.apply:
        print(json.dumps(summary, indent=2))
        return 2
    try:
        action = publish_durable_plan(args.output, plan)
    except (OSError, TranscriptV2BatchPublicationError) as error:
        parser.error(f"transcript-v2 plan publication failed: {error}")
    summary["action"] = action
    summary["status"] = "completed"
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
