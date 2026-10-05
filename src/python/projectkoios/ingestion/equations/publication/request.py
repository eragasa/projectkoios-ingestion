"""Named equation publication request."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.equations.publication.member import (
    EquationPublicationMember,
    EquationPublicationMemberName,
)


@dataclass(frozen=True, slots=True)
class EquationPublicationRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Four explicitly named create-once equation publication members."""

    CONTRACT_NAME: ClassVar[str] = "equation-publication-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    assembly: EquationPublicationMember
    recognition: EquationPublicationMember
    index: EquationPublicationMember
    derivation: EquationPublicationMember

    def __post_init__(self) -> None:
        self._validate_member(
            self.assembly,
            EquationPublicationMemberName.ASSEMBLY,
        )
        self._validate_member(
            self.recognition,
            EquationPublicationMemberName.RECOGNITION,
        )
        self._validate_member(
            self.index,
            EquationPublicationMemberName.INDEX,
        )
        self._validate_member(
            self.derivation,
            EquationPublicationMemberName.DERIVATION,
        )
        parents = {
            self.assembly.path.parent,
            self.recognition.path.parent,
            self.index.path.parent,
            self.derivation.path.parent,
        }
        if len(parents) != 1:
            raise ValueError(
                "equation publication members must share one directory"
            )

    @staticmethod
    def _validate_member(
        member: EquationPublicationMember,
        expected_name: EquationPublicationMemberName,
    ) -> None:
        if type(member) is not EquationPublicationMember:
            raise TypeError(
                f"equation publication {expected_name.value} member is invalid"
            )
        if member.name is not expected_name:
            raise ValueError(
                f"equation publication {expected_name.value} member is misnamed"
            )
