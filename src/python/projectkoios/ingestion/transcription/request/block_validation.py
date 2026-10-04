from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import ExtractedBlock
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)


@dataclass(frozen=True)
class TranscriptionBlockValidation(
    AbstractValidation, AbstractTranscriptionDataObject
):
    block: ExtractedBlock
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError(
                "unsupported transcription block validation version"
            )
        if not isinstance(self.block, ExtractedBlock):
            raise TypeError("transcription block validation requires a block")
        has_source_local_evidence = any(
            span.source_object_id is not None
            or span.bounding_box is not None
            or span.start_offset is not None
            for span in self.block.source_spans
        )
        fallback_payload = (
            None
            if has_source_local_evidence
            else (
                self.block.text,
                self.block.asset_id,
                self.block.asset_mask_id,
            )
        )
        expected = stable_id(
            "block",
            self.block.kind,
            tuple(span.identity_parts() for span in self.block.source_spans),
            fallback_payload,
        )
        if self.block.block_id != expected:
            raise ValueError("document block identity is stale")
