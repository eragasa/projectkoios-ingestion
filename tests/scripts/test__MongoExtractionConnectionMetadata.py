from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.mongodb_extraction_connection import (
    MongoExtractionConnectionMetadata,
)


def test__mongo_extraction_connection_metadata__loads_private_metadata(
    tmp_path: Path,
) -> None:
    recovery_root = tmp_path / "recovery"
    connection = tmp_path / "connection.json"
    connection.write_text(
        json.dumps(
            {
                "host": "127.0.0.1",
                "port": 27018,
                "replica_set": "projectkoiosDevelopment",
                "database": "projectkoios_ingestion_development",
                "application_username": "projectkoios-ingestion",
                "keychain_service": "projectkoios.mongodb.development",
                "recovery_root": str(recovery_root),
            }
        ),
        encoding="utf-8",
    )
    connection.chmod(0o600)

    metadata = MongoExtractionConnectionMetadata.load(connection)

    assert metadata.host == "127.0.0.1"
    assert metadata.port == 27018
    assert metadata.recovery_root == recovery_root.resolve()


def test__mongo_connection_metadata__rejects_symlink_traversal(
    tmp_path: Path,
) -> None:
    real_directory = tmp_path / "real"
    real_directory.mkdir()
    connection = real_directory / "connection.json"
    connection.write_text("{}", encoding="utf-8")
    connection.chmod(0o600)
    alias = tmp_path / "alias"
    alias.symlink_to(real_directory, target_is_directory=True)

    with pytest.raises(ValueError, match="cannot traverse a symlink"):
        MongoExtractionConnectionMetadata.load(alias / "connection.json")


def test__mongo_extraction_connection_metadata__rejects_broad_permissions(
    tmp_path: Path,
) -> None:
    connection = tmp_path / "connection.json"
    connection.write_text("{}", encoding="utf-8")
    connection.chmod(0o644)

    with pytest.raises(ValueError, match="permissions are too broad"):
        MongoExtractionConnectionMetadata.load(connection)
