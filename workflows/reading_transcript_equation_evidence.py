"""Recognition-independent equation projection for reading transcripts."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class ReadingTranscriptEquationEvidence:
    """One selected assembly projected without recognized equation text."""

    assembly_id: str
    candidate_ids: tuple[str, ...]
    selection_inventory_id: str
    native_text_evidence: str
    source_labels: tuple[str, ...]
    source_spans: tuple[
        tuple[int, tuple[float, float, float, float] | None], ...
    ]
    rendered_member: tuple[str, str, int]
    review_status: Literal["unreviewed"] = "unreviewed"
    accepted: Literal[False] = False
    review_required: Literal[True] = True
    chunk_text_eligible: Literal[False] = False

    @classmethod
    def from_selected_evidence(
        cls,
        *,
        selection_record: Mapping[str, object],
        assembly_evidence: Mapping[str, object],
        selection_inventory_id: str,
    ) -> ReadingTranscriptEquationEvidence:
        """Bind one selected record to its exact assembly evidence."""

        if type(selection_record) is not dict:
            raise TypeError("selection_record must be a dict")
        if type(assembly_evidence) is not dict:
            raise TypeError("assembly_evidence must be a dict")
        if (
            selection_record.get("disposition")
            != "selected_primary_equation_evidence"
        ):
            raise ValueError(
                "equation evidence is not selected primary evidence"
            )
        if (
            selection_record.get("review_status") != "unreviewed"
            or selection_record.get("accepted") is not False
            or selection_record.get("review_required") is not True
            or selection_record.get("chunk_text_eligible") is not False
            or selection_record.get("recognized_text_retained") is not False
        ):
            raise ValueError("selected equation review gates differ")
        assembly_id = selection_record.get("assembly_id")
        if type(assembly_id) is not str or assembly_id != assembly_evidence.get(
            "assembly_id"
        ):
            raise ValueError("selected equation assembly binding differs")
        candidate_values = selection_record.get("candidate_ids")
        if (
            type(candidate_values) is not list
            or candidate_values != assembly_evidence.get("candidate_ids")
            or not candidate_values
            or any(
                type(value) is not str or not value
                for value in candidate_values
            )
        ):
            raise ValueError("selected equation candidate binding differs")
        if (
            type(selection_inventory_id) is not str
            or re.fullmatch(
                r"reference-equation-evidence-selection-inventory:sha256:[0-9a-f]{64}",
                selection_inventory_id,
            )
            is None
        ):
            raise ValueError("selection inventory identity is invalid")
        native_text = assembly_evidence.get("sanitized_native_text")
        if type(native_text) is not str:
            raise TypeError("equation native text evidence must be a string")
        label_values = assembly_evidence.get("source_labels")
        if type(label_values) is not list or any(
            type(value) is not str for value in label_values
        ):
            raise TypeError("equation source labels must be a string list")
        span_values = assembly_evidence.get("source_spans")
        if type(span_values) is not list or not span_values:
            raise ValueError("equation source spans must be a nonempty list")
        source_spans: list[
            tuple[int, tuple[float, float, float, float] | None]
        ] = []
        for span in span_values:
            if type(span) is not dict:
                raise TypeError("equation source span must be a dict")
            page_index = span.get("page_index")
            box = span.get("bounding_box")
            if type(page_index) is not int or page_index < 0:
                raise ValueError("equation source span page index is invalid")
            normalized_box: tuple[float, float, float, float] | None
            if box is None:
                normalized_box = None
            elif (
                type(box) is not list
                or len(box) != 4
                or any(
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                    for value in box
                )
            ):
                raise ValueError("equation source bounding box is invalid")
            else:
                normalized_box = tuple(float(value) for value in box)  # type: ignore[assignment]
            source_spans.append((page_index, normalized_box))
        rendered = selection_record.get("assembly_rendered_member")
        if type(rendered) is not dict:
            raise ValueError("selected equation rendered member is missing")
        path = rendered.get("path")
        sha256 = rendered.get("sha256")
        byte_size = rendered.get("bytes")
        if type(path) is not str or not path:
            raise ValueError("selected equation rendered path is invalid")
        relative_path = PurePosixPath(path)
        if relative_path.is_absolute() or any(
            part in ("", ".", "..") for part in relative_path.parts
        ):
            raise ValueError("selected equation rendered path is invalid")
        if not SHA256Hash.is_canonical(sha256):
            raise ValueError("selected equation rendered hash is invalid")
        if type(byte_size) is not int or byte_size <= 0:
            raise ValueError("selected equation rendered byte size is invalid")
        return cls(
            assembly_id=assembly_id,
            candidate_ids=tuple(candidate_values),
            selection_inventory_id=selection_inventory_id,
            native_text_evidence=native_text,
            source_labels=tuple(label_values),
            source_spans=tuple(source_spans),
            rendered_member=(path, sha256, byte_size),
        )

    def to_record(self) -> dict[str, object]:
        """Return the canonical mutable page-composition record."""

        path, sha256, byte_size = self.rendered_member
        return {
            "evidence_type": "equation",
            "assembly_id": self.assembly_id,
            "candidate_ids": list(self.candidate_ids),
            "selection_disposition": "selected_primary_equation_evidence",
            "selection_inventory_id": self.selection_inventory_id,
            "recognition_status": "not_requested",
            "native_text_evidence": self.native_text_evidence,
            "source_labels": list(self.source_labels),
            "source_spans": [
                {
                    "page_index": page_index,
                    "bounding_box": list(box) if box is not None else None,
                }
                for page_index, box in self.source_spans
            ],
            "rendered_members": [
                {"path": path, "sha256": sha256, "bytes": byte_size}
            ],
            "recognized_latex": None,
            "recognized_mathml": None,
            "automated": True,
            "review_status": self.review_status,
            "accepted": self.accepted,
            "review_required": self.review_required,
            "chunk_text_eligible": self.chunk_text_eligible,
        }

    def __post_init__(self) -> None:
        if not self.assembly_id or not self.candidate_ids:
            raise ValueError("equation evidence identities are required")
        if len(self.candidate_ids) != len(set(self.candidate_ids)):
            raise ValueError("equation candidate identities must be unique")
        if (
            self.review_status != "unreviewed"
            or self.accepted is not False
            or self.review_required is not True
            or self.chunk_text_eligible is not False
        ):
            raise ValueError("equation evidence review gates are immutable")
