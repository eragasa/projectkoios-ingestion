"""Historical owner references for private PDF page-span sources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject

_OWNER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_MAXIMUM_PAGE_NUMBER = 9_999


@dataclass(frozen=True, slots=True)
class PrivatePdfPageSpanReference(AbstractImmutableDataObject):
    """Preserve one historical private PDF owner and page-span reference.

    This value describes Ingestion-owned source-document metadata. It does not
    identify or compare the referenced PDF bytes; ``SourceDocument.blob_id``
    and content-hash fields retain that separate responsibility.

    Parameters
    ----------
    owner
        Case-sensitive historical owner token, such as ``SzeNg3Ed``.
    first_page_number
        One-based first source page represented by the private PDF.
    last_page_number
        One-based inclusive last source page represented by the private PDF.
    source_id
        Historical owner/page-span source identifier.
    locator
        Historical non-public source locator.
    contract_version
        Version of this owner-specific reference contract.
    """

    CONTRACT_NAME: ClassVar[str] = (
        "projectkoios.ingestion.private-pdf-page-span-reference"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    owner: str
    first_page_number: int
    last_page_number: int
    source_id: str
    locator: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        owner: str,
        first_page_number: int,
        last_page_number: int,
    ) -> PrivatePdfPageSpanReference:
        """Create the exact retained source ID and locator for one span."""
        first, last = cls._require_parts(
            owner=owner,
            first_page_number=first_page_number,
            last_page_number=last_page_number,
        )
        return cls(
            owner=owner,
            first_page_number=first_page_number,
            last_page_number=last_page_number,
            source_id=f"private:{owner}:pages:{first}-{last}",
            locator=f"private://{owner}/pages-{first}-{last}.pdf",
        )

    def __post_init__(self) -> None:
        """Reject malformed or forged historical references."""
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported private PDF page-span contract")
        first, last = self._require_parts(
            owner=self.owner,
            first_page_number=self.first_page_number,
            last_page_number=self.last_page_number,
        )
        expected_source_id = f"private:{self.owner}:pages:{first}-{last}"
        expected_locator = f"private://{self.owner}/pages-{first}-{last}.pdf"
        if self.source_id != expected_source_id:
            raise ValueError("private PDF page-span source_id is inconsistent")
        if self.locator != expected_locator:
            raise ValueError("private PDF page-span locator is inconsistent")

    @staticmethod
    def _require_parts(
        *,
        owner: str,
        first_page_number: int,
        last_page_number: int,
    ) -> tuple[str, str]:
        if type(owner) is not str or _OWNER.fullmatch(owner) is None:
            raise ValueError("private PDF owner token is invalid")
        if (
            type(first_page_number) is not int
            or type(last_page_number) is not int
            or not 1 <= first_page_number <= last_page_number
            or last_page_number > _MAXIMUM_PAGE_NUMBER
        ):
            raise ValueError("private PDF page span is invalid")
        return f"{first_page_number:04d}", f"{last_page_number:04d}"
