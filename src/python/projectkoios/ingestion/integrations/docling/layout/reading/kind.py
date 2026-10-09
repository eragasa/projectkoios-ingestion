"""Docling reading-order direction and outcome taxonomies."""

from enum import StrEnum


class DoclingReadingOrderStatus(StrEnum):
    """Candidate-production outcome without resolution authority."""

    CANDIDATE_PRODUCED = "candidate_produced"
    UNRESOLVED = "unresolved"


class DoclingReadingOrderFailureKind(StrEnum):
    """Closed failure taxonomy for the optional Docling provider."""

    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_VERSION_MISMATCH = "provider_version_mismatch"
    UNSUPPORTED_DIRECTION = "unsupported_direction"
    UNSUPPORTED_REGION_KIND = "unsupported_region_kind"
    PROVIDER_FAILURE = "provider_failure"
    OUTPUT_TYPE_INVALID = "output_type_invalid"
    OUTPUT_ELEMENT_LIMIT_EXCEEDED = "output_element_limit_exceeded"
    OUTPUT_UNKNOWN_ELEMENT = "output_unknown_element"
    OUTPUT_DUPLICATE_ELEMENT = "output_duplicate_element"
    OUTPUT_INCOMPLETE = "output_incomplete"
