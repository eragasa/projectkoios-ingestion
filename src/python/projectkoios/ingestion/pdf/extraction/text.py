"""Deterministic composition of typed PDF block text evidence."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.base import (
    DataObjectActionizer,
    DataObjectActionRequest,
    DataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id

BLOCK_TEXT_ACTION_CONTRACT_VERSION = "1.0"
BLOCK_TEXT_ACTIONIZER_NAME = "deterministic-pdf-block-text-actionizer"
BLOCK_TEXT_ACTIONIZER_VERSION = "1"
MAXIMUM_BLOCK_TEXT_LINES = 100_000
MAXIMUM_BLOCK_TEXT_SPANS = 1_000_000
MAXIMUM_BLOCK_TEXT_CHARACTERS = 10_000_000


class BlockTextLimitError(ValueError):
    """Raised before block-text evidence exceeds a deterministic bound."""


@dataclass(frozen=True, slots=True)
class BlockTextRequest(DataObjectActionRequest):
    """Immutable text-span lines for one backend PDF block."""

    request_id: str
    lines: tuple[tuple[str, ...], ...]
    contract_version: str = BLOCK_TEXT_ACTION_CONTRACT_VERSION

    @classmethod
    def create(cls, *, lines: tuple[tuple[str, ...], ...]) -> BlockTextRequest:
        request_id = stable_id(
            "pdf-block-text-request",
            lines,
            BLOCK_TEXT_ACTION_CONTRACT_VERSION,
        )
        return cls(request_id=request_id, lines=lines)

    def __post_init__(self) -> None:
        if self.contract_version != BLOCK_TEXT_ACTION_CONTRACT_VERSION:
            raise ValueError("unsupported block-text request contract")
        if not isinstance(self.lines, tuple) or any(
            not isinstance(line, tuple)
            or any(not isinstance(text, str) for text in line)
            for line in self.lines
        ):
            raise TypeError("lines must contain immutable text-span tuples")
        if len(self.lines) > MAXIMUM_BLOCK_TEXT_LINES:
            raise BlockTextLimitError("block text lines exceed their limit")
        span_count = sum(len(line) for line in self.lines)
        if span_count > MAXIMUM_BLOCK_TEXT_SPANS:
            raise BlockTextLimitError("block text spans exceed their limit")
        character_count = sum(len(text) for line in self.lines for text in line)
        if character_count > MAXIMUM_BLOCK_TEXT_CHARACTERS:
            raise BlockTextLimitError(
                "block text characters exceed their limit"
            )
        expected = stable_id(
            "pdf-block-text-request",
            self.lines,
            self.contract_version,
        )
        if self.request_id != expected:
            raise ValueError("block-text request ID is inconsistent")


@dataclass(frozen=True, slots=True)
class BlockText(DataObjectActionResult):
    """Identified text composed for one exact block-text request."""

    result_id: str
    request_id: str
    text: str
    actionizer_name: str
    actionizer_version: str
    contract_version: str = BLOCK_TEXT_ACTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request: BlockTextRequest,
        text: str,
        actionizer_name: str,
        actionizer_version: str,
    ) -> BlockText:
        result_id = stable_id(
            "pdf-block-text-result",
            request.request_id,
            text,
            actionizer_name,
            actionizer_version,
            BLOCK_TEXT_ACTION_CONTRACT_VERSION,
        )
        return cls(
            result_id=result_id,
            request_id=request.request_id,
            text=text,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    def __post_init__(self) -> None:
        if self.contract_version != BLOCK_TEXT_ACTION_CONTRACT_VERSION:
            raise ValueError("unsupported block-text result contract")
        if not self.request_id:
            raise ValueError("request_id must be non-empty")
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")
        if not self.actionizer_name or not self.actionizer_version:
            raise ValueError("actionizer identity must be complete")
        expected = stable_id(
            "pdf-block-text-result",
            self.request_id,
            self.text,
            self.actionizer_name,
            self.actionizer_version,
            self.contract_version,
        )
        if self.result_id != expected:
            raise ValueError("block-text result ID is inconsistent")


class BlockTextActionizer(DataObjectActionizer[BlockTextRequest, BlockText]):
    """Compose deterministic block text from typed backend line evidence."""

    __slots__ = ()

    actionizer_name = BLOCK_TEXT_ACTIONIZER_NAME
    actionizer_version = BLOCK_TEXT_ACTIONIZER_VERSION

    def action(self, *, request: BlockTextRequest) -> BlockText:
        if not isinstance(request, BlockTextRequest):
            raise TypeError("request must be a BlockTextRequest")
        lines: list[str] = []
        for spans in request.lines:
            text = "".join(spans).rstrip()
            if text:
                lines.append(text)
        return BlockText.create(
            request=request,
            text="\n".join(lines),
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )


__all__ = [
    "BLOCK_TEXT_ACTION_CONTRACT_VERSION",
    "BLOCK_TEXT_ACTIONIZER_NAME",
    "BLOCK_TEXT_ACTIONIZER_VERSION",
    "MAXIMUM_BLOCK_TEXT_CHARACTERS",
    "MAXIMUM_BLOCK_TEXT_LINES",
    "MAXIMUM_BLOCK_TEXT_SPANS",
    "BlockText",
    "BlockTextLimitError",
    "BlockTextActionizer",
    "BlockTextRequest",
]
