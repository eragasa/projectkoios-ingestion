"""Shared provenance identity helpers."""

from projectkoios.ingestion.identity import stable_id


def _artifact_id(value: object) -> str:
    for name in (
        "result_id",
        "analysis_id",
        "manifest_id",
        "artifact_id",
        "document_id",
    ):
        identity = getattr(value, name, None)
        if isinstance(identity, str) and identity:
            return identity
    return stable_id(
        "derivation-audit-anonymous-artifact", type(value).__name__
    )


def _object_id(value: object) -> str | None:
    for name in (
        "result_id",
        "analysis_id",
        "artifact_id",
        "document_id",
        "manifest_id",
        "candidate_id",
        "structure_id",
        "item_id",
        "region_id",
        "block_id",
        "node_id",
        "selection_result_id",
        "selection_id",
        "work_item_id",
        "request_id",
        "input_id",
        "page_id",
        "source_id",
    ):
        identity = getattr(value, name, None)
        if isinstance(identity, str) and identity:
            return identity
    return None
