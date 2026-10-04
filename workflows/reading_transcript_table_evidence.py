"""Table evidence projection for recognition-independent transcripts."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CANDIDATE_PATTERN = re.compile(r"^table-candidate:sha256:[0-9a-f]{64}$")
_REGION_PATTERN = re.compile(r"^table-region-evidence:sha256:[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ReadingTranscriptTableEvidence:
    """One canonical, page-specific table evidence record."""

    candidate_id: str
    page_index: int
    canonical_bytes: bytes
    rendered_paths: tuple[str, ...]
    region_evidence_ids: tuple[str, ...]

    @classmethod
    def from_quality_evidence(
        cls,
        *,
        table_evidence: Mapping[str, object],
        rendered_members: list[dict[str, object]],
    ) -> tuple[ReadingTranscriptTableEvidence, ...]:
        """Project a quality-inventory table into page-specific records."""

        if type(table_evidence) is not dict:
            raise TypeError("table evidence must be a dict")
        if type(rendered_members) is not list or any(
            type(member) is not dict for member in rendered_members
        ):
            raise TypeError("table rendered members must be a dict list")

        candidate_id = table_evidence.get("candidate_id")
        evidence_status = table_evidence.get("evidence_status")
        confidence = table_evidence.get("confidence")
        boundary_kind = table_evidence.get("boundary_kind")
        source_label = table_evidence.get("source_label")
        source_spans = table_evidence.get("source_spans")
        associations = table_evidence.get("associations")
        expected_paths = table_evidence.get("rendered_members")
        expected_region_ids = table_evidence.get("region_evidence_ids")
        if type(candidate_id) is not str or not _CANDIDATE_PATTERN.fullmatch(
            candidate_id
        ):
            raise ValueError("table candidate identity is invalid")
        if evidence_status not in ("proposed", "ambiguous"):
            raise ValueError("table evidence status is invalid")
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not math.isfinite(float(confidence))
            or not 0.0 <= float(confidence) <= 1.0
        ):
            raise ValueError("table confidence is invalid")
        if boundary_kind not in ("ruled", "unruled", "mixed"):
            raise ValueError("table boundary kind is invalid")
        if source_label is not None and type(source_label) is not str:
            raise ValueError("table source label is invalid")
        if type(source_spans) is not list or not source_spans:
            raise ValueError("table source spans are required")
        if type(associations) is not list:
            raise ValueError("table associations must be a list")
        if (
            type(expected_paths) is not list
            or type(expected_region_ids) is not list
            or not expected_paths
            or len(expected_paths) != len(expected_region_ids)
            or len(expected_paths) != len(rendered_members)
            or any(type(path) is not str for path in expected_paths)
            or any(type(value) is not str for value in expected_region_ids)
        ):
            raise ValueError("table rendered-region coverage differs")

        spans_by_page: dict[int, list[dict[str, object]]] = {}
        for span in source_spans:
            page_index = cls._source_span_page(span)
            spans_by_page.setdefault(page_index, []).append(span)

        members_by_page: dict[int, list[dict[str, object]]] = {}
        for expected_path, expected_region_id, member in zip(
            expected_paths,
            expected_region_ids,
            rendered_members,
            strict=True,
        ):
            (
                path,
                sha256,
                byte_size,
                member_candidate_id,
                page_index,
                region_id,
            ) = cls._rendered_member_values(member)
            path_value = PurePosixPath(path)
            expected_value = PurePosixPath(expected_path)
            if (
                expected_value.is_absolute()
                or any(part in ("", ".", "..") for part in expected_value.parts)
                or path_value.parts[-len(expected_value.parts) :]
                != expected_value.parts
                or member_candidate_id != candidate_id
                or region_id != expected_region_id
            ):
                raise ValueError("table rendered-region binding differs")
            members_by_page.setdefault(page_index, []).append(
                {
                    "path": path,
                    "sha256": sha256,
                    "bytes": byte_size,
                    "region_evidence_id": region_id,
                }
            )
        if set(members_by_page) != set(spans_by_page):
            raise ValueError("table page coverage differs")
        if len(set(expected_region_ids)) != len(expected_region_ids):
            raise ValueError("table region identity is duplicated")

        records: list[ReadingTranscriptTableEvidence] = []
        for page_index in sorted(members_by_page):
            members = members_by_page[page_index]
            record = {
                "evidence_type": "table",
                "candidate_id": candidate_id,
                "evidence_status": evidence_status,
                "confidence": confidence,
                "boundary_kind": boundary_kind,
                "source_label": source_label,
                "source_spans": spans_by_page[page_index],
                "associations": associations,
                "rendered_members": members,
                "automated": True,
                "accepted": False,
                "review_required": True,
            }
            records.append(
                cls(
                    candidate_id=candidate_id,
                    page_index=page_index,
                    canonical_bytes=cls._canonical(record),
                    rendered_paths=tuple(
                        str(member["path"]) for member in members
                    ),
                    region_evidence_ids=tuple(
                        str(member["region_evidence_id"]) for member in members
                    ),
                )
            )
        return tuple(records)

    def to_record(self) -> dict[str, object]:
        """Return a detached mutable representation of the canonical record."""

        value = json.loads(self.canonical_bytes)
        if type(value) is not dict:
            raise RuntimeError("canonical table evidence is not an object")
        return value

    def __post_init__(self) -> None:
        if type(
            self.candidate_id
        ) is not str or not _CANDIDATE_PATTERN.fullmatch(self.candidate_id):
            raise ValueError("table candidate identity is invalid")
        if type(self.page_index) is not int or self.page_index < 0:
            raise ValueError("table page index is invalid")
        if type(self.canonical_bytes) is not bytes or not self.canonical_bytes:
            raise ValueError("canonical table evidence bytes are required")
        value = json.loads(self.canonical_bytes)
        if type(value) is not dict or self.canonical_bytes != self._canonical(
            value
        ):
            raise ValueError("table evidence bytes are not canonical")
        status = value.get("evidence_status")
        confidence = value.get("confidence")
        boundary_kind = value.get("boundary_kind")
        source_label = value.get("source_label")
        if (
            value.get("candidate_id") != self.candidate_id
            or value.get("evidence_type") != "table"
            or value.get("automated") is not True
            or value.get("accepted") is not False
            or value.get("review_required") is not True
            or status not in ("proposed", "ambiguous")
            or isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not math.isfinite(float(confidence))
            or not 0.0 <= float(confidence) <= 1.0
            or boundary_kind not in ("ruled", "unruled", "mixed")
            or (source_label is not None and type(source_label) is not str)
            or type(value.get("associations")) is not list
        ):
            raise ValueError("table evidence immutable fields differ")
        spans = value.get("source_spans")
        if (
            type(spans) is not list
            or not spans
            or any(
                self._source_span_page(span) != self.page_index
                for span in spans
            )
        ):
            raise ValueError("table page binding differs")
        members = value.get("rendered_members")
        if (
            type(members) is not list
            or not members
            or any(type(member) is not dict for member in members)
        ):
            raise ValueError("table rendered members are invalid")
        observed = tuple(
            self._projected_member_values(member) for member in members
        )
        if (
            tuple(value[0] for value in observed) != self.rendered_paths
            or tuple(value[3] for value in observed) != self.region_evidence_ids
            or len(set(self.region_evidence_ids))
            != len(self.region_evidence_ids)
        ):
            raise ValueError("table rendered-region binding differs")

    @staticmethod
    def _source_span_page(span: object) -> int:
        if type(span) is not dict:
            raise ValueError("table source span must be a dict")
        page_index = span.get("page_index")
        box = span.get("bounding_box")
        if type(page_index) is not int or page_index < 0:
            raise ValueError("table source page is invalid")
        if box is not None and (
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
            raise ValueError("table source bounding box is invalid")
        return page_index

    @staticmethod
    def _rendered_member_values(
        member: dict[str, object],
    ) -> tuple[str, str, int, str, int, str]:
        path = member.get("path")
        sha256 = member.get("sha256")
        byte_size = member.get("bytes")
        candidate_id = member.get("candidate_id")
        page_index = member.get("page_index")
        region_id = member.get("region_evidence_id")
        if type(path) is not str or not path:
            raise ValueError("table rendered path is invalid")
        path_value = PurePosixPath(path)
        if path_value.is_absolute() or any(
            part in ("", ".", "..") for part in path_value.parts
        ):
            raise ValueError("table rendered path is invalid")
        if type(sha256) is not str or not _SHA256_PATTERN.fullmatch(sha256):
            raise ValueError("table rendered hash is invalid")
        if type(byte_size) is not int or byte_size <= 0:
            raise ValueError("table rendered byte count is invalid")
        if type(candidate_id) is not str or not _CANDIDATE_PATTERN.fullmatch(
            candidate_id
        ):
            raise ValueError("table rendered candidate identity is invalid")
        if type(page_index) is not int or page_index < 0:
            raise ValueError("table rendered page is invalid")
        if type(region_id) is not str or not _REGION_PATTERN.fullmatch(
            region_id
        ):
            raise ValueError("table region identity is invalid")
        return path, sha256, byte_size, candidate_id, page_index, region_id

    @staticmethod
    def _projected_member_values(
        member: dict[str, object],
    ) -> tuple[str, str, int, str]:
        path = member.get("path")
        sha256 = member.get("sha256")
        byte_size = member.get("bytes")
        region_id = member.get("region_evidence_id")
        if type(path) is not str or not path:
            raise ValueError("table rendered path is invalid")
        path_value = PurePosixPath(path)
        if path_value.is_absolute() or any(
            part in ("", ".", "..") for part in path_value.parts
        ):
            raise ValueError("table rendered path is invalid")
        if type(sha256) is not str or not _SHA256_PATTERN.fullmatch(sha256):
            raise ValueError("table rendered hash is invalid")
        if type(byte_size) is not int or byte_size <= 0:
            raise ValueError("table rendered byte count is invalid")
        if type(region_id) is not str or not _REGION_PATTERN.fullmatch(
            region_id
        ):
            raise ValueError("table region identity is invalid")
        return path, sha256, byte_size, region_id

    @staticmethod
    def _canonical(value: object) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
