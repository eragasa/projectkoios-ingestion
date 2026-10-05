"""Payload-specific projector failures."""

from projectkoios.ingestion.base.projector.error import ProjectionContractError


class ProjectionPayloadError(ProjectionContractError):
    """Report malformed or noncanonical serialized projection evidence.

    Notes
    -----
    Use this error only when a projector consumes a serialized payload and that
    payload fails syntax, canonicalization, completeness, or structural checks.
    Identity disagreements use ``ProjectionIdentityError``; declared type
    mismatches use ``ProjectionContractError`` directly.
    """
