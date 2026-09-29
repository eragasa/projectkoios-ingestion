"""Generic bounded contract graph and identity audit walker."""

from __future__ import annotations

import hashlib
import math
from dataclasses import fields, is_dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedPage,
    Metadata,
    SourceDocument,
    SourceSpan,
)
from projectkoios.ingestion.pdf.models import RenderedRegion
from projectkoios.ingestion.provenance import (
    _BOX_TOLERANCE,
    _MAX_VISITED_OBJECTS,
    DerivationAuditFindingCode,
    DerivationAuditLimitError,
)
from projectkoios.ingestion.provenance.common import _object_id


class _ContractAuditWalker:
    if TYPE_CHECKING:
        source: SourceDocument
        pages: dict[int, ExtractedPage]
        blocks: dict[str, ExtractedBlock]
        _seen_objects: set[int]
        _visited_count: int

        def _add(
            self,
            code: DerivationAuditFindingCode,
            path: str,
            message: str,
            object_id: str | None = None,
            evidence: Metadata = (),
        ) -> None: ...

        def _orphan(self, path: str, object_id: str) -> None: ...

    def _walk(self, value: object, path: str) -> None:
        if isinstance(
            value, (str, bytes, int, float, bool, type(None), StrEnum)
        ):
            return
        if isinstance(value, tuple):
            for index, item in enumerate(value):
                self._walk(item, f"{path}[{index}]")
            return
        if not is_dataclass(value):
            return
        identity = id(value)
        if identity in self._seen_objects:
            return
        self._seen_objects.add(identity)
        self._visited_count += 1
        if self._visited_count > _MAX_VISITED_OBJECTS:
            raise DerivationAuditLimitError(
                f"audit exceeds {_MAX_VISITED_OBJECTS} retained objects"
            )
        self._audit_intrinsic(value, path)
        self._audit_common(value, path)
        for field_info in fields(value):
            self._walk(
                getattr(value, field_info.name), f"{path}.{field_info.name}"
            )

    def _audit_intrinsic(self, value: object, path: str) -> None:
        post_init = getattr(value, "__post_init__", None)
        if post_init is None:
            return
        try:
            post_init()
        except (AssertionError, TypeError, ValueError) as error:
            self._add(
                DerivationAuditFindingCode.INTRINSIC_CONTRACT_VIOLATION,
                path,
                f"{type(value).__name__} violates its intrinsic "
                f"contract: {error}",
                _object_id(value),
            )

    def _audit_common(self, value: object, path: str) -> None:
        object_id = _object_id(value)
        if isinstance(value, SourceDocument) and value != self.source:
            self._add(
                DerivationAuditFindingCode.SOURCE_DOCUMENT_MISMATCH,
                path,
                "embedded source document differs from the audit root source",
                value.source_id,
            )
        source_id = getattr(value, "source_id", None)
        if source_id is not None and source_id != self.source.source_id:
            self._add(
                DerivationAuditFindingCode.SOURCE_ID_MISMATCH,
                f"{path}.source_id",
                "derived object refers to a different source ID",
                object_id,
            )
        source_blob_id = getattr(value, "source_blob_id", None)
        if source_blob_id is not None and source_blob_id != self.source.blob_id:
            self._add(
                DerivationAuditFindingCode.SOURCE_BLOB_MISMATCH,
                f"{path}.source_blob_id",
                "derived object refers to a different source blob",
                object_id,
            )
        source_hash = getattr(value, "source_content_hash", None)
        if source_hash is not None and source_hash != self.source.content_hash:
            self._add(
                DerivationAuditFindingCode.SOURCE_HASH_MISMATCH,
                f"{path}.source_content_hash",
                "derived object refers to a different source hash",
                object_id,
            )
        if isinstance(value, SourceSpan):
            self._audit_span(value, path)
        page_index = getattr(value, "page_index", None)
        if isinstance(page_index, int) and not isinstance(page_index, bool):
            if page_index not in self.pages:
                self._add(
                    DerivationAuditFindingCode.PAGE_OUT_OF_RANGE,
                    f"{path}.page_index",
                    "derived object refers to a page outside the root document",
                    object_id,
                    (("page_index", str(page_index)),),
                )
            else:
                self._audit_source_boxes(value, path, page_index)
        self._audit_processor_identity(value, path)
        self._audit_content_identity(value, path)
        self._audit_block_references(value, path)

    def _audit_span(self, span: SourceSpan, path: str) -> None:
        page = self.pages.get(span.page_index)
        if page is None:
            return
        if (
            span.printed_page_label is not None
            and span.printed_page_label != page.printed_page_label
        ):
            self._add(
                DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                f"{path}.printed_page_label",
                "source span printed label differs from its root page",
                span.source_object_id,
            )
        if span.bounding_box is not None:
            self._check_box(
                span.bounding_box,
                page.width,
                page.height,
                path,
                span.source_object_id,
            )
        if (
            span.source_object_id in self.blocks
            and span.start_offset is not None
            and self.blocks[span.source_object_id].text is not None
            and span.end_offset is not None
            and span.end_offset
            > len(self.blocks[span.source_object_id].text or "")
        ):
            self._add(
                DerivationAuditFindingCode.REGION_OUT_OF_RANGE,
                path,
                "source span text offsets exceed the referenced block",
                span.source_object_id,
            )

    def _audit_source_boxes(
        self, value: object, path: str, page_index: int
    ) -> None:
        page = self.pages[page_index]
        page_width = getattr(value, "page_width", None)
        page_height = getattr(value, "page_height", None)
        if page_width is not None and page_width != page.width:
            self._add(
                DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                f"{path}.page_width",
                "derived page width differs from the root page",
                _object_id(value),
            )
        if page_height is not None and page_height != page.height:
            self._add(
                DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                f"{path}.page_height",
                "derived page height differs from the root page",
                _object_id(value),
            )
        coordinate_system = getattr(value, "coordinate_system", None)
        if (
            coordinate_system is not None
            and coordinate_system != page.coordinate_system
        ):
            self._add(
                DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                f"{path}.coordinate_system",
                "derived coordinate system differs from the root page",
                _object_id(value),
            )
        rotation = getattr(value, "rotation_degrees", None)
        if rotation is not None and rotation != page.rotation_degrees:
            self._add(
                DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                f"{path}.rotation_degrees",
                "derived page rotation differs from the root page",
                _object_id(value),
            )
        for name in (
            "bounding_box",
            "source_bounding_box",
            "effective_source_bounding_box",
        ):
            box = getattr(value, name, None)
            if box is not None:
                self._check_box(
                    box,
                    page.width,
                    page.height,
                    f"{path}.{name}",
                    _object_id(value),
                )
        start = getattr(value, "start", None)
        end = getattr(value, "end", None)
        if (
            isinstance(start, tuple)
            and len(start) == 2
            and isinstance(end, tuple)
            and len(end) == 2
        ):
            for point_name, point in (("start", start), ("end", end)):
                if (
                    any(
                        isinstance(item, bool)
                        or not isinstance(item, (int, float))
                        or not math.isfinite(item)
                        for item in point
                    )
                    or point[0] < -_BOX_TOLERANCE
                    or point[1] < -_BOX_TOLERANCE
                    or point[0] > page.width + _BOX_TOLERANCE
                    or point[1] > page.height + _BOX_TOLERANCE
                ):
                    self._add(
                        DerivationAuditFindingCode.REGION_OUT_OF_RANGE,
                        f"{path}.{point_name}",
                        "source point lies outside the root page extent",
                        _object_id(value),
                    )
        if isinstance(value, RenderedRegion):
            if value.page_rotation_degrees != page.rotation_degrees:
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{path}.page_rotation_degrees",
                    "rendered region rotation differs from its root page",
                    value.region_id,
                )

    def _check_box(
        self,
        box: object,
        width: float,
        height: float,
        path: str,
        object_id: str | None,
    ) -> None:
        if (
            not isinstance(box, tuple)
            or len(box) != 4
            or any(
                isinstance(item, bool)
                or not isinstance(item, (int, float))
                or not math.isfinite(item)
                for item in box
            )
        ):
            self._add(
                DerivationAuditFindingCode.REGION_OUT_OF_RANGE,
                path,
                "source bounding box is not a finite four-coordinate tuple",
                object_id,
            )
            return
        x0, y0, x1, y1 = box
        if (
            x0 < -_BOX_TOLERANCE
            or y0 < -_BOX_TOLERANCE
            or x1 > width + _BOX_TOLERANCE
            or y1 > height + _BOX_TOLERANCE
            or x1 < x0
            or y1 < y0
        ):
            self._add(
                DerivationAuditFindingCode.REGION_OUT_OF_RANGE,
                path,
                "source bounding box lies outside the root page extent",
                object_id,
                (
                    ("box", repr(box)),
                    ("page_extent", repr((0.0, 0.0, width, height))),
                ),
            )

    def _audit_processor_identity(self, value: object, path: str) -> None:
        for prefix in ("processor", "backend", "extractor"):
            name_field = f"{prefix}_name"
            version_field = f"{prefix}_version"
            has_name = hasattr(value, name_field)
            has_version = hasattr(value, version_field)
            if not (has_name or has_version):
                continue
            name = getattr(value, name_field, None)
            version = getattr(value, version_field, None)
            if (
                not isinstance(name, str)
                or not name
                or not isinstance(version, str)
                or not version
            ):
                self._add(
                    DerivationAuditFindingCode.PROCESSOR_IDENTITY_MISSING,
                    path,
                    f"{prefix} name and version must both be non-empty",
                    _object_id(value),
                )
        if hasattr(value, "configuration_digest"):
            digest = value.configuration_digest
            if not isinstance(digest, str) or not digest:
                self._add(
                    DerivationAuditFindingCode.PROCESSOR_IDENTITY_MISSING,
                    f"{path}.configuration_digest",
                    "processor configuration digest is missing",
                    _object_id(value),
                )
        if hasattr(value, "contract_version"):
            contract_version = value.contract_version
            if not isinstance(contract_version, str) or not contract_version:
                self._add(
                    DerivationAuditFindingCode.CONTRACT_VERSION_MISSING,
                    f"{path}.contract_version",
                    "artifact contract version is missing",
                    _object_id(value),
                )

    def _audit_content_identity(self, value: object, path: str) -> None:
        if not all(
            hasattr(value, name)
            for name in ("content", "content_sha256", "byte_length")
        ):
            return
        content_value: Any = value
        content = content_value.content
        digest = content_value.content_sha256
        byte_length = content_value.byte_length
        if isinstance(content, bytes) and (
            hashlib.sha256(content).hexdigest() != digest
            or len(content) != byte_length
        ):
            self._add(
                DerivationAuditFindingCode.CONTENT_IDENTITY_MISMATCH,
                path,
                "retained content bytes do not match their hash or byte length",
                _object_id(value),
            )

    def _audit_block_references(self, value: object, path: str) -> None:
        if isinstance(value, ExtractedBlock):
            return
        for field_name in ("block_id", "source_block_id"):
            block_id = getattr(value, field_name, None)
            if isinstance(block_id, str) and block_id not in self.blocks:
                self._orphan(f"{path}.{field_name}", block_id)
        for field_name in (
            "block_ids",
            "source_block_ids",
            "input_block_ids",
            "raw_block_ids",
            "non_text_block_ids",
            "merged_cell_signal_block_ids",
        ):
            block_ids = getattr(value, field_name, None)
            if isinstance(block_ids, tuple):
                for block_id in block_ids:
                    if (
                        isinstance(block_id, str)
                        and block_id not in self.blocks
                    ):
                        self._orphan(f"{path}.{field_name}", block_id)
