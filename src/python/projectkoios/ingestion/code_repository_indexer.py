from __future__ import annotations

from projectkoios.ingestion.code_repository_ingester import (
    CodeRepositoryIngester,
)
from projectkoios.ingestion.protocols import ChunkIndexWriter
from projectkoios.repositories.code import CodeRepository


class CodeRepositoryIndexer:
    def __init__(
        self,
        ingester: CodeRepositoryIngester,
        index_writer: ChunkIndexWriter,
    ) -> None:
        self.ingester = ingester
        self.index_writer = index_writer

    def index_repository(
        self,
        repository: CodeRepository,
    ) -> None:
        chunks = self.ingester.iter_chunks(repository)
        self.index_writer.add_chunks(chunks)
