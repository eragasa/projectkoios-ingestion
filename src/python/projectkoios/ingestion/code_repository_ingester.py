from __future__ import annotations

from collections.abc import Iterator

from projectkoios.chunking import LineChunker, TextChunk
from projectkoios.repositories.code import (
    CodeRepository,
    CodeRepositoryLoader,
)


class CodeRepositoryIngester:
    def __init__(
        self,
        loader: CodeRepositoryLoader,
        chunker: LineChunker,
    ) -> None:
        self.loader = loader
        self.chunker = chunker

    def iter_chunks(
        self,
        repository: CodeRepository,
    ) -> Iterator[TextChunk]:
        for code_file in self.loader.iter_files(repository):
            yield from self.chunker.chunk_text(
                text=code_file.text,
                source_path=code_file.relative_path,
                source_kind="code_file",
                language=code_file.language,
            )
