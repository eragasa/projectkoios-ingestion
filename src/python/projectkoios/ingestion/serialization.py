from __future__ import annotations

from projectkoios.ingestion.identity import canonical_json, to_json_value


def serialize_contract(value: object) -> str:
    """Serialize an ingestion contract using canonical JSON."""
    return canonical_json(value)


def contract_dict(value: object) -> dict[str, object]:
    """Convert an ingestion contract to a JSON-compatible dictionary."""
    serialized = to_json_value(value)
    if not isinstance(serialized, dict):
        raise TypeError("contract root must serialize to a JSON object")
    return serialized
