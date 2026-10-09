"""Bounded deterministic identities for pure page projection."""

from __future__ import annotations

from collections.abc import Sequence

from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)
from projectkoios.ingestion.page.projection.limits.error import (
    PageProjectionLimitError,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


def fingerprint_page_projection_identity(
    *,
    namespace: str,
    material: object,
) -> str:
    """Serialize validated material once, enforce its bound, and fingerprint."""
    namespace_value = PAGE_PROJECTION_LIMITS.require_identity(
        namespace, "identity namespace"
    )
    if ":" in namespace_value:
        raise ValueError("identity namespace cannot contain a colon")
    serialized = CanonicalJsonSerializer.serialize_bytes(material)
    if len(serialized) > PAGE_PROJECTION_LIMITS.maximum_identity_input_bytes:
        raise PageProjectionLimitError("identity input exceeds its limit")
    digest = SHA256Fingerprinter.fingerprint(content=serialized)
    return f"{namespace_value}:sha256:{digest}"


class PageProjectionInputIdentityDerivation:
    """Derive one request identity from exact current input bindings."""

    __slots__ = ()

    @classmethod
    def derive(
        cls,
        *,
        source_result_id: str,
        artifact_verification_result_id: str,
        include_figure_captions: bool,
        contract_version: str,
    ) -> str:
        """Return the bounded deterministic page-projection request ID."""
        del cls
        return fingerprint_page_projection_identity(
            namespace="page-projection-request",
            material={
                "artifact_verification_result_id": (
                    artifact_verification_result_id
                ),
                "contract_version": contract_version,
                "include_figure_captions": include_figure_captions,
                "source_result_id": source_result_id,
            },
        )


class PageProjectionResultIdentityDerivation:
    """Derive bounded identities for projected values and one result."""

    __slots__ = ()

    @classmethod
    def derive_block(
        cls,
        *,
        order_index: int,
        text: str,
        style: str,
        source_id: str,
    ) -> str:
        """Return one exact projected text-block identity."""
        del cls
        return fingerprint_page_projection_identity(
            namespace="page-projection-text-block",
            material={
                "order_index": order_index,
                "source_id": source_id,
                "style": style,
                "text": text,
            },
        )

    @classmethod
    def derive_block_inventory(
        cls,
        *,
        block_ids: Sequence[str],
    ) -> str:
        """Return one exact ordered block-inventory identity."""
        del cls
        return fingerprint_page_projection_identity(
            namespace="page-projection-text-block-inventory",
            material={"block_ids": list(block_ids)},
        )

    @classmethod
    def derive_page(
        cls,
        *,
        source_page_id: str,
        location_id: str,
        block_inventory_id: str,
    ) -> str:
        """Return one exact citation-aligned projected-page identity."""
        del cls
        return fingerprint_page_projection_identity(
            namespace="page-projection-page",
            material={
                "block_inventory_id": block_inventory_id,
                "location_id": location_id,
                "source_page_id": source_page_id,
            },
        )

    @classmethod
    def derive_page_inventory(
        cls,
        *,
        page_ids: Sequence[str],
    ) -> str:
        """Return one exact ordered page-inventory identity."""
        del cls
        return fingerprint_page_projection_identity(
            namespace="page-projection-page-inventory",
            material={"page_ids": list(page_ids)},
        )

    @classmethod
    def derive_limitation_inventory(
        cls,
        *,
        limitations: Sequence[str],
    ) -> str:
        """Return one exact mandatory scope-limitation identity."""
        del cls
        return fingerprint_page_projection_identity(
            namespace="page-projection-limitation-inventory",
            material={"limitations": list(limitations)},
        )

    @classmethod
    def derive_window_inventory(
        cls,
        *,
        source_inventory_id: str,
        window_size: int,
        window_inventory_ids: Sequence[str],
    ) -> str:
        """Return one grouping identity without changing page semantics."""
        del cls
        return fingerprint_page_projection_identity(
            namespace="page-projection-page-window-inventory",
            material={
                "source_inventory_id": source_inventory_id,
                "window_inventory_ids": list(window_inventory_ids),
                "window_size": window_size,
            },
        )

    @classmethod
    def derive(
        cls,
        *,
        request_id: str,
        source_id: str,
        page_inventory_id: str,
        limitation_inventory_id: str,
        reading_limitation_inventory_id: str,
        processor_id: str,
        processor_version: str,
        contract_version: str,
    ) -> str:
        """Return the bounded deterministic page-projection result ID."""
        del cls
        return fingerprint_page_projection_identity(
            namespace="page-projection-result",
            material={
                "contract_version": contract_version,
                "limitation_inventory_id": limitation_inventory_id,
                "page_inventory_id": page_inventory_id,
                "processor_id": processor_id,
                "processor_version": processor_version,
                "reading_limitation_inventory_id": (
                    reading_limitation_inventory_id
                ),
                "request_id": request_id,
                "source_id": source_id,
            },
        )
