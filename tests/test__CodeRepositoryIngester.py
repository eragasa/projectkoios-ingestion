from pathlib import Path

from projectkoios.chunking import LineChunker
from projectkoios.ingestion import CodeRepositoryIngester
from projectkoios.repositories.code import CodeRepository, CodeRepositoryLoader


def test__iter_chunks__yields_chunks_from_code_repository(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "example"
    repo_root.mkdir()

    source_file = repo_root / "main.py"
    source_file.write_text("print('hello')\n", encoding="utf-8")

    repository = CodeRepository(root=repo_root, name="example")
    loader = CodeRepositoryLoader()
    chunker = LineChunker(lines_per_chunk=10, overlap_lines=0)
    ingester = CodeRepositoryIngester(loader=loader, chunker=chunker)

    chunks = list(ingester.iter_chunks(repository))

    assert len(chunks) == 1
    assert chunks[0].text == "print('hello')\n"


def test__iter_chunks__preserves_relative_source_path(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "example"
    source_dir = repo_root / "src" / "projectkoios"
    source_dir.mkdir(parents=True)

    source_file = source_dir / "app.py"
    source_file.write_text("app = None\n", encoding="utf-8")

    repository = CodeRepository(root=repo_root, name="example")
    loader = CodeRepositoryLoader()
    chunker = LineChunker(lines_per_chunk=10, overlap_lines=0)
    ingester = CodeRepositoryIngester(loader=loader, chunker=chunker)

    chunks = list(ingester.iter_chunks(repository))

    assert len(chunks) == 1
    assert chunks[0].source_path == Path("src/projectkoios/app.py")


def test__iter_chunks__sets_source_kind_to_code_file(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "example"
    repo_root.mkdir()

    source_file = repo_root / "main.py"
    source_file.write_text("print('hello')\n", encoding="utf-8")

    repository = CodeRepository(root=repo_root, name="example")
    loader = CodeRepositoryLoader()
    chunker = LineChunker(lines_per_chunk=10, overlap_lines=0)
    ingester = CodeRepositoryIngester(loader=loader, chunker=chunker)

    chunks = list(ingester.iter_chunks(repository))

    assert len(chunks) == 1
    assert chunks[0].source_kind == "code_file"


def test__iter_chunks__preserves_language(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "example"
    repo_root.mkdir()

    source_file = repo_root / "pyproject.toml"
    source_file.write_text("[project]\nname = 'example'\n", encoding="utf-8")

    repository = CodeRepository(root=repo_root, name="example")
    loader = CodeRepositoryLoader()
    chunker = LineChunker(lines_per_chunk=10, overlap_lines=0)
    ingester = CodeRepositoryIngester(loader=loader, chunker=chunker)

    chunks = list(ingester.iter_chunks(repository))

    assert len(chunks) == 1
    assert chunks[0].language == "toml"
