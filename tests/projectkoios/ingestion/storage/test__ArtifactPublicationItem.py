from pathlib import Path

import pytest
from projectkoios.ingestion.storage.artifact import ArtifactPublicationItem


def test__artifact_publication_item__requires_named_path_and_text(
    tmp_path: Path,
) -> None:
    item = ArtifactPublicationItem(
        path=tmp_path / "artifact.json",
        text="{}\n",
    )

    assert item.path.name == "artifact.json"
    assert item.text == "{}\n"
    with pytest.raises(TypeError, match="text"):
        ArtifactPublicationItem(
            path=tmp_path / "artifact.json",
            text=b"{}",  # type: ignore[arg-type]
        )
