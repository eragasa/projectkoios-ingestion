from pathlib import Path

import pytest
from projectkoios.ingestion.equations.publication.error import (
    EquationPublicationInventoryError,
)
from projectkoios.ingestion.equations.publication.inventory import (
    inspect_equation_publication_inventory,
    require_equation_publication_inventory,
)
from projectkoios.ingestion.equations.publication.status import (
    EquationPublicationInventoryStatus,
)


def test__publication_inventory__distinguishes_none_complete_and_partial(
    tmp_path: Path,
) -> None:
    root = tmp_path / "publication"
    root.mkdir()

    empty = require_equation_publication_inventory(root)
    assert empty.status is EquationPublicationInventoryStatus.NONE

    (root / "recognition.json").write_text("{}", encoding="utf-8")
    partial = inspect_equation_publication_inventory(root)
    assert partial.status is EquationPublicationInventoryStatus.PARTIAL
    assert partial.problem_codes == ("index_missing",)
    with pytest.raises(EquationPublicationInventoryError, match="partial"):
        require_equation_publication_inventory(root)

    (root / "index.json").write_text("{}", encoding="utf-8")
    complete = require_equation_publication_inventory(root)
    assert complete.status is EquationPublicationInventoryStatus.COMPLETE_PAIR
    assert complete.problem_codes == ()


def test__publication_inventory__rejects_symlink_member(
    tmp_path: Path,
) -> None:
    root = tmp_path / "publication"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    (root / "recognition.json").symlink_to(outside)
    (root / "index.json").write_text("{}", encoding="utf-8")

    inventory = inspect_equation_publication_inventory(root)

    assert inventory.status is EquationPublicationInventoryStatus.PARTIAL
    assert inventory.problem_codes == ("recognition_unsafe",)
    with pytest.raises(
        EquationPublicationInventoryError,
        match="recognition_unsafe",
    ):
        require_equation_publication_inventory(root)
