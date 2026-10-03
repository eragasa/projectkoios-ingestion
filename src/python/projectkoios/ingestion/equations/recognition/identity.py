"""Stable equation-recognition identities."""

from projectkoios.ingestion.identity import stable_id

EQUATION_RECOGNITION_CONTRACT_VERSION = "1.0"


def equation_recognition_request_id(
    assembly_artifact_id: str,
    processor_identity_digest: str,
) -> str:
    """Return the legacy-stable identity for one recognition request."""

    return stable_id(
        "equation-recognition-request",
        EQUATION_RECOGNITION_CONTRACT_VERSION,
        assembly_artifact_id,
        processor_identity_digest,
    )
