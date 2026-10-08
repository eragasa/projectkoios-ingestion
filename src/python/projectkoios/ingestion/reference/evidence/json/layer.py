"""JSON mapping for nested audited-layer counts."""

from dataclasses import dataclass

from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.reference.evidence.json.value import (
    REFERENCE_EVIDENCE_JSON_VALUE_READER,
    ReferenceEvidenceJsonValueReader,
)
from projectkoios.ingestion.reference.evidence.layer import (
    ReferenceEvidenceLayerCount,
)


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceLayerCountJsonCodec:
    """Project and reconstruct one audited-layer-count wire object."""

    reader: ReferenceEvidenceJsonValueReader

    def to_json_value(
        self,
        count: ReferenceEvidenceLayerCount,
    ) -> dict[str, JsonValue]:
        if not isinstance(count, ReferenceEvidenceLayerCount):
            raise TypeError("value must be a ReferenceEvidenceLayerCount")
        return {"layer": count.layer, "count": count.count}

    def from_json_value(
        self,
        value: JsonValue,
        *,
        index: int,
    ) -> ReferenceEvidenceLayerCount:
        mapping = self.reader.mapping(
            value,
            f"derivation_audit.audited_layer_counts[{index}]",
            {"layer", "count"},
        )
        return ReferenceEvidenceLayerCount(
            layer=self.reader.text(
                mapping["layer"],
                f"derivation_audit.audited_layer_counts[{index}].layer",
            ),
            count=self.reader.integer(
                mapping["count"],
                f"derivation_audit.audited_layer_counts[{index}].count",
            ),
        )


REFERENCE_EVIDENCE_LAYER_COUNT_JSON_CODEC = (
    ReferenceEvidenceLayerCountJsonCodec(REFERENCE_EVIDENCE_JSON_VALUE_READER)
)
