from __future__ import annotations

import argparse
import json
from pathlib import Path

from projectkoios.ingestion.integrations.disk.extraction.store import (
    DiskExtractionPublicationStore,
)
from projectkoios.ingestion.integrations.mongodb.extraction.store import (
    MongoExtractionPublicationStore,
)
from projectkoios.ingestion.storage.extraction.error import (
    ExtractionPublicationError,
)
from projectkoios.ingestion.storage.extraction.recovery.request import (
    ExtractionProjectionRecoveryRequest,
)
from pymongo.errors import PyMongoError

from scripts.mongodb_extraction_connection import (
    MongoExtractionConnectionMetadata,
    open_mongo_extraction_client,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.extraction_projection_recovery",
        description=(
            "Rebuild an extraction MongoDB projection from its authoritative "
            "disk journal. The command is a dry run unless --apply is supplied."
        ),
    )
    parser.add_argument(
        "--connection",
        type=Path,
        required=True,
        help="private connection.json written by notebook provisioning",
    )
    parser.add_argument(
        "--maximum-records",
        type=int,
        default=1_000_000,
        help="maximum journal records accepted during recovery",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform authenticated projection recovery",
    )
    return parser


def main() -> None:
    parser = _parser()
    arguments = parser.parse_args()
    try:
        metadata = MongoExtractionConnectionMetadata.load(arguments.connection)
        request = ExtractionProjectionRecoveryRequest.create(
            maximum_records=arguments.maximum_records,
        )
        journal_path = metadata.recovery_root / "publications.jsonl"
        if not arguments.apply:
            print(
                json.dumps(
                    {
                        "apply": False,
                        "database": metadata.database,
                        "host": metadata.host,
                        "journal_exists": journal_path.is_file(),
                        "port": metadata.port,
                        "recovery_request_id": request.request_id,
                        "recovery_root": str(metadata.recovery_root),
                        "replica_set": metadata.replica_set,
                    },
                    sort_keys=True,
                )
            )
            return
        with open_mongo_extraction_client(metadata) as client:
            journal = DiskExtractionPublicationStore(metadata.recovery_root)
            store = MongoExtractionPublicationStore(
                database=client[metadata.database],
                journal=journal,
                projection_target=metadata.extraction_projection_target(),
                default_write_authority_id=(
                    "authority:extraction-projection-recovery-cli"
                ),
            )
            result = store.recover(request=request)
        print(
            json.dumps(
                {
                    "apply": True,
                    "database": metadata.database,
                    "last_journal_sequence": result.last_journal_sequence,
                    "observed_records": result.observed_records,
                    "projected_records": result.projected_records,
                    "recovery_request_id": result.request_id,
                },
                sort_keys=True,
            )
        )
    except (
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
