from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def test__extraction_publication_script__dry_run_is_non_mutating(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).parents[2]
    recovery_root = tmp_path / "recovery"
    connection = tmp_path / "connection.json"
    connection.write_text(
        json.dumps(
            {
                "host": "127.0.0.1",
                "port": 27018,
                "replica_set": "projectkoiosDevelopment",
                "database": "projectkoios_ingestion_development",
                "environment": "development",
                "application_username": "projectkoios-ingestion",
                "keychain_service": "projectkoios.mongodb.development",
                "recovery_root": str(recovery_root),
            }
        ),
        encoding="utf-8",
    )
    connection.chmod(0o600)
    source = tmp_path / "source.pdf"
    content = b"%PDF dry-run fixture"
    source.write_bytes(content)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.extraction_publication",
            str(source),
            "--source-id",
            "source:dry-run",
            "--expected-source-sha256",
            hashlib.sha256(content).hexdigest(),
            "--expected-source-byte-size",
            str(len(content)),
            "--connection",
            str(connection),
        ],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["apply"] is False
    assert result["source_id"] == "source:dry-run"
    assert not recovery_root.exists()


def test__extraction_publication_script__help_is_available() -> None:
    repository = Path(__file__).parents[2]

    completed = subprocess.run(
        [sys.executable, "-m", "scripts.extraction_publication", "--help"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "--expected-source-sha256" in completed.stdout
    assert "--connection" in completed.stdout
    assert "--apply" in completed.stdout
