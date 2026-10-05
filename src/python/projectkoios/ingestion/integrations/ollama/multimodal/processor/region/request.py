from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import canonical_json, stable_id
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    _HARD_MAX_SELECTIONS,
    _HARD_MAX_TOTAL_IMAGE_BYTES,
    _HARD_MAX_TOTAL_PIXELS,
    OllamaMultimodalLimitError,
    OllamaMultimodalSelection,
    OllamaMultimodalTaskKind,
    OllamaPromptRecord,
)


@dataclass(frozen=True)
class OllamaMultimodalRegionProcessingRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    CONTRACT_NAME: ClassVar[str] = "ollama-multimodal-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request_id: str
    task_kind: OllamaMultimodalTaskKind
    selections: tuple[OllamaMultimodalSelection, ...]
    prompt: OllamaPromptRecord

    @classmethod
    def _build_prompt(
        cls,
        selections: tuple[OllamaMultimodalSelection, ...],
    ) -> OllamaPromptRecord:
        manifest = canonical_json(
            [
                {
                    "index": index,
                    "selection_id": item.selection_id,
                    "source_id": item.source_id,
                    "source_blob_id": item.source_blob_id,
                    "source_content_hash": item.source_content_hash,
                    "page_index": item.page_index,
                    "region_id": item.region_id,
                    "png_sha256": item.png_sha256,
                    "png_byte_length": item.png_byte_length,
                    "width_pixels": item.width_pixels,
                    "height_pixels": item.height_pixels,
                }
                for index, item in enumerate(selections)
            ]
        )
        text = OllamaPromptRecord.TEMPLATE.format(
            prompt_version=OllamaPromptRecord.CONTRACT_VERSION,
            manifest=manifest,
        )
        encoded = text.encode("utf-8")
        return OllamaPromptRecord(
            version=OllamaPromptRecord.CONTRACT_VERSION,
            template_sha256=OllamaPromptRecord._prompt_template_sha256(),
            rendered_sha256=OllamaPromptRecord._sha256_bytes(encoded),
            utf8_byte_length=len(encoded),
            text=text,
        )

    @classmethod
    def _request_id(
        cls,
        task_kind: OllamaMultimodalTaskKind,
        selections: tuple[OllamaMultimodalSelection, ...],
        prompt: OllamaPromptRecord,
    ) -> str:
        return stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            task_kind,
            tuple(
                (
                    identity.selection_id,
                    identity.source_id,
                    identity.source_blob_id,
                    identity.source_content_hash,
                    identity.page_index,
                    identity.region_id,
                    identity.png_sha256,
                    identity.png_byte_length,
                    identity.width_pixels,
                    identity.height_pixels,
                )
                for identity in (item.identity for item in selections)
            ),
            prompt,
        )

    @classmethod
    def create(
        cls,
        selections: tuple[OllamaMultimodalSelection, ...],
        *,
        task_kind: OllamaMultimodalTaskKind = (
            OllamaMultimodalTaskKind.PAGE_REGION_TRANSCRIPTION
        ),
    ) -> OllamaMultimodalRegionProcessingRequest:
        if not isinstance(selections, tuple):
            raise TypeError("selections must be an immutable tuple")
        if not selections:
            raise OllamaMultimodalLimitError(
                "at least one multimodal selection is required"
            )
        if len(selections) > _HARD_MAX_SELECTIONS:
            raise OllamaMultimodalLimitError("too many multimodal selections")
        if any(
            not isinstance(item, OllamaMultimodalSelection)
            for item in selections
        ):
            raise TypeError(
                "selections must contain OllamaMultimodalSelection values"
            )
        if not isinstance(task_kind, OllamaMultimodalTaskKind):
            raise TypeError("task_kind must be OllamaMultimodalTaskKind")
        if len({item.selection_id for item in selections}) != len(selections):
            raise ValueError("multimodal selection IDs must be unique")
        total_bytes = sum(item.png_byte_length for item in selections)
        total_pixels = sum(
            item.width_pixels * item.height_pixels for item in selections
        )
        if total_bytes > _HARD_MAX_TOTAL_IMAGE_BYTES:
            raise OllamaMultimodalLimitError(
                "selection PNGs exceed the aggregate byte limit"
            )
        if total_pixels > _HARD_MAX_TOTAL_PIXELS:
            raise OllamaMultimodalLimitError(
                "selection PNGs exceed the aggregate pixel limit"
            )
        prompt = cls._build_prompt(selections)
        request_id = cls._request_id(task_kind, selections, prompt)
        return cls(
            request_id=request_id,
            task_kind=task_kind,
            selections=selections,
            prompt=prompt,
        )

    def __post_init__(self) -> None:
        if not isinstance(self.selections, tuple) or not self.selections:
            raise ValueError("request selections must be a nonempty tuple")
        if any(
            not isinstance(item, OllamaMultimodalSelection)
            for item in self.selections
        ):
            raise TypeError(
                "selections must contain OllamaMultimodalSelection values"
            )
        if not isinstance(self.task_kind, OllamaMultimodalTaskKind):
            raise TypeError("task_kind must be OllamaMultimodalTaskKind")
        if len(self.selections) > _HARD_MAX_SELECTIONS:
            raise OllamaMultimodalLimitError("too many multimodal selections")
        if len({item.selection_id for item in self.selections}) != len(
            self.selections
        ):
            raise ValueError("multimodal selection IDs must be unique")
        if sum(item.png_byte_length for item in self.selections) > (
            _HARD_MAX_TOTAL_IMAGE_BYTES
        ):
            raise OllamaMultimodalLimitError(
                "selection PNGs exceed the aggregate byte limit"
            )
        if (
            sum(
                item.width_pixels * item.height_pixels
                for item in self.selections
            )
            > _HARD_MAX_TOTAL_PIXELS
        ):
            raise OllamaMultimodalLimitError(
                "selection PNGs exceed the aggregate pixel limit"
            )
        expected_prompt = self._build_prompt(self.selections)
        if self.prompt != expected_prompt:
            raise ValueError("request prompt is not canonical for selections")
        expected_id = self._request_id(
            self.task_kind,
            self.selections,
            self.prompt,
        )
        if self.request_id != expected_id:
            raise ValueError("request identity mismatch")
