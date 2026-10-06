"""Figure evidence projection for recognition-independent transcripts."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath

from projectkoios.ingestion.sha256.hash import SHA256Hash

_CANDIDATE_PATTERN = re.compile(r"^figure-candidate:sha256:[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ReadingTranscriptFigureEvidence:
    """One canonical, unreviewed figure evidence record."""

    candidate_id: str
    page_index: int
    canonical_bytes: bytes
    rendered_paths: tuple[str, ...]

    @classmethod
    def from_quality_evidence(
        cls,
        *,
        figure_evidence: Mapping[str, object],
        rendered_members: list[dict[str, object]],
    ) -> ReadingTranscriptFigureEvidence:
        """Project one quality-inventory figure using verified member metadata."""

        if type(figure_evidence) is not dict:
            raise TypeError("figure evidence must be a dict")
        if type(rendered_members) is not list or any(
            type(member) is not dict for member in rendered_members
        ):
            raise TypeError("figure rendered members must be a dict list")

        candidate_id = figure_evidence.get("candidate_id")
        evidence_status = figure_evidence.get("evidence_status")
        confidence = figure_evidence.get("confidence")
        source_label = figure_evidence.get("source_label")
        source_spans = figure_evidence.get("source_spans")
        associations = figure_evidence.get("associations")
        expected_members = figure_evidence.get("rendered_members")
        if type(candidate_id) is not str or not _CANDIDATE_PATTERN.fullmatch(
            candidate_id
        ):
            raise ValueError("figure candidate identity is invalid")
        if evidence_status not in ("proposed", "ambiguous"):
            raise ValueError("figure evidence status is invalid")
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not math.isfinite(float(confidence))
            or not 0.0 <= float(confidence) <= 1.0
        ):
            raise ValueError("figure confidence is invalid")
        if source_label is not None and type(source_label) is not str:
            raise ValueError("figure source label is invalid")
        if type(source_spans) is not list or not source_spans:
            raise ValueError("figure source spans are required")
        if type(associations) is not list:
            raise ValueError("figure associations must be a list")
        if (
            type(expected_members) is not list
            or not expected_members
            or any(type(path) is not str for path in expected_members)
            or len(expected_members) != len(rendered_members)
        ):
            raise ValueError("figure rendered-member coverage differs")

        page_index = cls._page_index(source_spans)

        projected_members: list[dict[str, object]] = []
        rendered_paths: list[str] = []
        for expected_path, member in zip(
            expected_members, rendered_members, strict=True
        ):
            path, sha256, byte_size = cls._rendered_member_values(member)
            path_value = PurePosixPath(path)
            expected_value = PurePosixPath(expected_path)
            if (
                expected_value.is_absolute()
                or any(part in ("", ".", "..") for part in expected_value.parts)
                or path_value.parts[-len(expected_value.parts) :]
                != expected_value.parts
            ):
                raise ValueError("figure rendered path binding differs")
            projected_members.append(
                {"path": path, "sha256": sha256, "bytes": byte_size}
            )
            rendered_paths.append(path)

        record = {
            "evidence_type": "figure",
            "candidate_id": candidate_id,
            "evidence_status": evidence_status,
            "confidence": confidence,
            "source_label": source_label,
            "source_spans": source_spans,
            "associations": associations,
            "rendered_members": projected_members,
            "automated": True,
            "accepted": False,
            "review_required": True,
        }
        return cls(
            candidate_id=candidate_id,
            page_index=page_index,
            canonical_bytes=cls._canonical(record),
            rendered_paths=tuple(rendered_paths),
        )

    def to_record(self) -> dict[str, object]:
        """Return a detached mutable representation of the canonical record."""

        value = json.loads(self.canonical_bytes)
        if type(value) is not dict:
            raise RuntimeError("canonical figure evidence is not an object")
        return value

    def __post_init__(self) -> None:
        if type(
            self.candidate_id
        ) is not str or not _CANDIDATE_PATTERN.fullmatch(self.candidate_id):
            raise ValueError("figure candidate identity is invalid")
        if type(self.page_index) is not int or self.page_index < 0:
            raise ValueError("figure page index is invalid")
        if type(self.canonical_bytes) is not bytes or not self.canonical_bytes:
            raise ValueError("canonical figure evidence bytes are required")
        value = json.loads(self.canonical_bytes)
        if type(value) is not dict or self.canonical_bytes != self._canonical(
            value
        ):
            raise ValueError("figure evidence bytes are not canonical")
        status = value.get("evidence_status")
        confidence = value.get("confidence")
        source_label = value.get("source_label")
        if (
            value.get("candidate_id") != self.candidate_id
            or value.get("evidence_type") != "figure"
            or value.get("automated") is not True
            or value.get("accepted") is not False
            or value.get("review_required") is not True
            or status not in ("proposed", "ambiguous")
            or isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not math.isfinite(float(confidence))
            or not 0.0 <= float(confidence) <= 1.0
            or (source_label is not None and type(source_label) is not str)
            or type(value.get("associations")) is not list
        ):
            raise ValueError("figure evidence immutable fields differ")
        spans = value.get("source_spans")
        if (
            type(spans) is not list
            or self._page_index(spans) != self.page_index
        ):
            raise ValueError("figure page binding differs")
        members = value.get("rendered_members")
        if (
            type(members) is not list
            or not members
            or any(type(member) is not dict for member in members)
        ):
            raise ValueError("figure rendered members are invalid")
        observed_paths = tuple(
            self._rendered_member_values(member)[0] for member in members
        )
        if observed_paths != self.rendered_paths:
            raise ValueError("figure rendered paths differ")

    @staticmethod
    def _page_index(source_spans: list[object]) -> int:
        page_indexes: set[int] = set()
        for span in source_spans:
            if type(span) is not dict:
                raise ValueError("figure source span must be a dict")
            page_index = span.get("page_index")
            box = span.get("bounding_box")
            if type(page_index) is not int or page_index < 0:
                raise ValueError("figure source page is invalid")
            page_indexes.add(page_index)
            if box is None:
                continue
            if (
                type(box) is not list
                or len(box) != 4
                or any(
                    isinstance(coordinate, bool)
                    or not isinstance(coordinate, (int, float))
                    or not math.isfinite(float(coordinate))
                    for coordinate in box
                )
                or float(box[0]) > float(box[2])
                or float(box[1]) > float(box[3])
            ):
                raise ValueError("figure source bounding box is invalid")
        if len(page_indexes) != 1:
            raise ValueError("figure evidence must bind to one page")
        return next(iter(page_indexes))

    @staticmethod
    def _rendered_member_values(
        member: dict[str, object],
    ) -> tuple[str, str, int]:
        path = member.get("path")
        sha256 = member.get("sha256")
        byte_size = member.get("bytes")
        if type(path) is not str or not path:
            raise ValueError("figure rendered path is invalid")
        path_value = PurePosixPath(path)
        if path_value.is_absolute() or any(
            part in ("", ".", "..") for part in path_value.parts
        ):
            raise ValueError("figure rendered path is invalid")
        if not SHA256Hash.is_canonical(sha256):
            raise ValueError("figure rendered hash is invalid")
        if type(byte_size) is not int or byte_size <= 0:
            raise ValueError("figure rendered byte count is invalid")
        return path, sha256, byte_size

    @staticmethod
    def _canonical(value: object) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
