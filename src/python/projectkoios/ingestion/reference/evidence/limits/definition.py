"""Immutable resource ceilings owned by reference evidence."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceLimits:
    """Own the fixed record, identity, artifact, and JSON ceilings."""

    maximum_document_bytes: int = field(default=262_144, init=False)
    maximum_identity_input_bytes: int = field(default=262_144, init=False)
    maximum_lineage_identities: int = field(default=4_096, init=False)
    maximum_layout_identities: int = field(default=512, init=False)
    maximum_layer_counts: int = field(default=32, init=False)
    maximum_limitations: int = field(default=32, init=False)
    maximum_bound_artifact_bytes: int = field(
        default=128_000_000,
        init=False,
    )
    maximum_string_characters: int = field(default=4_096, init=False)
    maximum_json_container_depth: int = field(default=64, init=False)
    maximum_json_items: int = field(default=8_192, init=False)
    maximum_json_string_bytes: int = field(default=16_384, init=False)
    maximum_json_total_string_bytes: int = field(
        default=262_144,
        init=False,
    )
    maximum_json_number_characters: int = field(default=4_096, init=False)
    maximum_artifact_json_items: int = field(
        default=20_000_000,
        init=False,
    )


REFERENCE_EVIDENCE_LIMITS = ReferenceEvidenceLimits()
