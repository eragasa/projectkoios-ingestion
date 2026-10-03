from dataclasses import replace
from pathlib import Path

import pytest
from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.equations.publication.member import (
    EquationPublicationMember,
    EquationPublicationMemberName,
)
from projectkoios.ingestion.equations.publication.request import (
    EquationPublicationRequest,
)


def _member(
    root: Path,
    name: EquationPublicationMemberName,
) -> EquationPublicationMember:
    return EquationPublicationMember(
        name=name,
        path=root / f"{name.value}.json",
        content="{}\n",
    )


def test__equation_publication_request__uses_named_members(
    tmp_path: Path,
) -> None:
    request = EquationPublicationRequest(
        assembly=_member(tmp_path, EquationPublicationMemberName.ASSEMBLY),
        recognition=_member(
            tmp_path,
            EquationPublicationMemberName.RECOGNITION,
        ),
        index=_member(tmp_path, EquationPublicationMemberName.INDEX),
        derivation=_member(
            tmp_path,
            EquationPublicationMemberName.DERIVATION,
        ),
    )

    assert isinstance(request, DataObjectActionRequest)
    with pytest.raises(ValueError, match="assembly member is misnamed"):
        replace(request, assembly=request.recognition)
