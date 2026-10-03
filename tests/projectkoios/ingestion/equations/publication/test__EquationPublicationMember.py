from pathlib import Path

import pytest
from projectkoios.ingestion.equations.publication.member import (
    EquationPublicationMember,
    EquationPublicationMemberName,
)


def test__equation_publication_member__binds_name_path_and_content(
    tmp_path: Path,
) -> None:
    member = EquationPublicationMember(
        name=EquationPublicationMemberName.DERIVATION,
        path=tmp_path / "derivation.json",
        content="{}\n",
    )

    assert member.name is EquationPublicationMemberName.DERIVATION
    with pytest.raises(ValueError, match="newline JSON"):
        EquationPublicationMember(
            name=EquationPublicationMemberName.DERIVATION,
            path=tmp_path / "derivation.json",
            content="{}",
        )
