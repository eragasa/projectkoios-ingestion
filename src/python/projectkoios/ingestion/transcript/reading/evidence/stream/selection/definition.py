"""Explicit reading text stream selection."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.derivation import (  # noqa: E501
    ReadingEvidenceIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.inventory import (  # noqa: E501
    ReadingTextStreamEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.kind import (
    ReadingTextStreamKind,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.selection.basis import (  # noqa: E501
    ReadingTextSelectionBasis,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingTextSelection:
    """Select exactly one retained page stream without erasing alternatives."""

    selection_id: ReadingEvidenceIdentity
    page_location: ReadingPageLocation
    selected_stream_id: ReadingEvidenceIdentity
    basis: ReadingTextSelectionBasis
    producer_id: ReadingEvidenceIdentity
    composition_id: ReadingEvidenceIdentity | None

    def __init__(
        self,
        *,
        streams: ReadingTextStreamEvidenceInventory,
        selected_stream_id: ReadingEvidenceIdentity,
        basis: ReadingTextSelectionBasis,
    ) -> None:
        if type(streams) is not ReadingTextStreamEvidenceInventory:
            raise TypeError(
                "streams must be ReadingTextStreamEvidenceInventory"
            )
        if not isinstance(basis, ReadingTextSelectionBasis):
            raise TypeError("basis must be ReadingTextSelectionBasis")
        selected = streams.require(selected_stream_id)
        expected_kind = (
            ReadingTextStreamKind.NATIVE
            if basis is ReadingTextSelectionBasis.NATIVE_EXACT
            else ReadingTextStreamKind.OCR
        )
        if selected.kind is not expected_kind:
            raise ReadingEvidenceError(
                f"{expected_kind.value} selection must select its matching "
                "stream"
            )
        values = {
            "page_location": streams.page_location,
            "selected_stream_id": selected.stream_id,
            "basis": basis,
            "producer_id": selected.producer_id,
            "composition_id": selected.composition_id,
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(
            self,
            "selection_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.TEXT_SELECTION,
                prefix="reading-text-selection",
                material={
                    "page_location_id": streams.page_location.location_id.value,
                    "selected_stream_id": selected.stream_id.value,
                    "basis": basis,
                    "producer_id": selected.producer_id.value,
                    "composition_id": (
                        None
                        if selected.composition_id is None
                        else selected.composition_id.value
                    ),
                },
            ),
        )

    def validate_against(
        self, streams: ReadingTextStreamEvidenceInventory
    ) -> None:
        """Require this selection to match one exact stream inventory."""
        if self != ReadingTextSelection(
            streams=streams,
            selected_stream_id=self.selected_stream_id,
            basis=self.basis,
        ):
            raise ReadingEvidenceError(
                "text selection is inconsistent with its streams"
            )
