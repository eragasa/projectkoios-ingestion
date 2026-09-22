from __future__ import annotations

import argparse
import json
from pathlib import Path

from projectkoios.ingestion.cli import ExtractionCacheOperationError
from projectkoios.ingestion.transcript_v2_batch import (
    TRANSCRIPT_V2_BATCH_MANIFEST_SCHEMA_VERSION,
    TranscriptV2BatchPublicationError,
    execute_transcript_v2_batch_item,
    load_durable_plan,
    resolve_transcript_v2_batch_plan,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="koios-compose-pdf-transcripts-v2-batch"
    )
    parser.add_argument("plan", type=Path)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--ingestion-root", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--apply", action="store_true")
    return parser


def main(arguments: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(arguments)
    try:
        plan = load_durable_plan(args.plan)
        resolved = resolve_transcript_v2_batch_plan(
            plan,
            source_root=args.source_root,
            ingestion_root=args.ingestion_root,
        )
    except (OSError, ValueError) as error:
        parser.error(f"invalid transcript-v2 batch plan: {error}")
    if not args.apply:
        print(
            json.dumps(
                {
                    "artifact_generation": plan.artifact_generation,
                    "items": [
                        {
                            "action": (
                                "verify_existing"
                                if item.existing
                                else "create"
                            ),
                            "output_directory": (
                                item.plan_item.output_directory.as_posix()
                            ),
                            "source_id": item.plan_item.source_id,
                        }
                        for item in resolved
                    ],
                    "manifest_schema_version": (
                        TRANSCRIPT_V2_BATCH_MANIFEST_SCHEMA_VERSION
                    ),
                    "plan_id": plan.plan_id,
                    "status": "planned",
                },
                indent=2,
            )
        )
        return 2

    completed: list[dict[str, object]] = []
    try:
        for item in resolved:
            completed.append(
                execute_transcript_v2_batch_item(
                    item,
                    plan=plan,
                    cache_root=args.cache_root,
                )
            )
    except (
        ExtractionCacheOperationError,
        OSError,
        TranscriptV2BatchPublicationError,
        ValueError,
    ) as error:
        parser.error(
            "transcript-v2 batch stopped after "
            f"{len(completed)} completed items: {error}"
        )
    print(
        json.dumps(
            {
                "artifact_generation": plan.artifact_generation,
                "items": completed,
                "manifest_schema_version": (
                    TRANSCRIPT_V2_BATCH_MANIFEST_SCHEMA_VERSION
                ),
                "plan_id": plan.plan_id,
                "status": "completed",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
