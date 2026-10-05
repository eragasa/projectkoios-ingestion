"""Private notebook MongoDB connection composition for repository commands."""

from __future__ import annotations

import json
import re
import stat
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from projectkoios.ingestion.storage.extraction.error import (
    ExtractionPublicationError,
)
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from pymongo import MongoClient


@dataclass(frozen=True, slots=True)
class MongoExtractionConnectionMetadata:
    """Validated non-secret metadata for one local extraction projection."""

    MAX_METADATA_BYTES: ClassVar[int] = 65_536
    NAME: ClassVar[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_.-]{1,128}")

    host: str
    port: int
    replica_set: str
    database: str
    environment: str
    application_username: str
    keychain_service: str
    recovery_root: Path

    @classmethod
    def load(cls, path: Path) -> MongoExtractionConnectionMetadata:
        if not isinstance(path, Path):
            raise TypeError("connection metadata path must be a Path")
        source = path.expanduser().absolute()
        if source.resolve() != source:
            raise ValueError("connection metadata cannot traverse a symlink")
        if source.is_symlink() or not source.is_file():
            raise ValueError("connection metadata path is missing or unsafe")
        if stat.S_IMODE(source.stat().st_mode) & 0o077:
            raise ValueError("connection metadata permissions are too broad")
        content = source.read_bytes()
        if not content or len(content) > cls.MAX_METADATA_BYTES:
            raise ValueError("connection metadata size is out of bounds")
        value = json.loads(content)
        if type(value) is not dict:
            raise ValueError("connection metadata root must be an object")
        host = value.get("host")
        port = value.get("port")
        if host != "127.0.0.1":
            raise ValueError(
                "extraction command requires a loopback MongoDB host"
            )
        if isinstance(port, bool) or not isinstance(port, int):
            raise ValueError("MongoDB port is invalid")
        if not 1 <= port <= 65_535:
            raise ValueError("MongoDB port is out of bounds")
        recovery_root = value.get("recovery_root")
        if type(recovery_root) is not str or not recovery_root:
            raise ValueError("connection metadata recovery root is invalid")
        return cls(
            host=host,
            port=port,
            replica_set=cls._required_name(
                value.get("replica_set"), "replica set"
            ),
            database=cls._required_name(value.get("database"), "database"),
            environment=cls._required_name(
                value.get("environment"), "environment"
            ),
            application_username=cls._required_name(
                value.get("application_username"), "username"
            ),
            keychain_service=cls._required_name(
                value.get("keychain_service"), "Keychain service"
            ),
            recovery_root=Path(recovery_root).expanduser().resolve(),
        )

    def extraction_projection_target(
        self,
    ) -> ExtractionProjectionTargetIdentity:
        """Return the explicit extraction read-projection target identity."""
        return ExtractionProjectionTargetIdentity.create(
            deployment_id=self.replica_set,
            environment=self.environment,
            database_name=self.database,
            schema_id="extraction-read-model-v1",
            projection_slot="authoritative-extraction-read-model",
        )

    @classmethod
    def _required_name(cls, value: object, label: str) -> str:
        if type(value) is not str or not cls.NAME.fullmatch(value):
            raise ValueError(f"connection metadata {label} is invalid")
        return value


@contextmanager
def open_mongo_extraction_client(
    metadata: MongoExtractionConnectionMetadata,
) -> Iterator[MongoClient[dict[str, Any]]]:
    """Open an authenticated client without persisting its password."""

    if type(metadata) is not MongoExtractionConnectionMetadata:
        raise TypeError("metadata must be MongoExtractionConnectionMetadata")
    completed = subprocess.run(
        [
            "/usr/bin/security",
            "find-generic-password",
            "-s",
            metadata.keychain_service,
            "-a",
            metadata.application_username,
            "-w",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    password = completed.stdout.rstrip("\n")
    if completed.returncode != 0 or not password:
        raise ExtractionPublicationError(
            "MongoDB application credential is unavailable in Keychain"
        )
    client: MongoClient[dict[str, Any]] = MongoClient(
        host=metadata.host,
        port=metadata.port,
        username=metadata.application_username,
        password=password,
        authSource=metadata.database,
        replicaSet=metadata.replica_set,
        serverSelectionTimeoutMS=5_000,
    )
    try:
        client.admin.command("ping")
        yield client
    finally:
        client.close()
