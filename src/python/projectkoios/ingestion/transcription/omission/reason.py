from __future__ import annotations

from enum import StrEnum


class TranscriptionOmissionReason(StrEnum):
    REPRESENTED_BY_TYPED_OBJECT = "represented_by_typed_object"
    REPRESENTED_BY_EARLIER_ITEM = "represented_by_earlier_item"
    NO_TEXT_PAYLOAD = "no_text_payload"
    UNREPRESENTED_NON_TEXT_BLOCK = "unrepresented_non_text_block"
