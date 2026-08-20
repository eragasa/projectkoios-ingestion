# ADR20260629: Establish projectkoios-ingestion repository

## Status

Accepted

## Context

The Project Koios monorepo was split per ADR20260626 (mothership + extracted repos). The mothership's `projectkoios.ingestion` package contained the code repository ingestion pipeline — the first stable, unit-tested component that could be extracted without breaking existing consumers.

The ingestion pipeline coordinates loading a code repository, chunking its files, and writing the resulting chunks to an index. It consists of three objects:

- `CodeRepositoryIngester` — takes a loader and chunker, yields `TextChunk` objects
- `CodeRepositoryIndexer` — wires an ingester to a `ChunkIndexWriter` to index a repository
- `ChunkIndexWriter` — a protocol defining the output contract for ingestion consumers

These objects depend on shared packages that remain in the mothership (`projectkoios.chunking`, `projectkoios.repositories.code`), and they depend on each other.

## Decision

1. Establish `projectkoios-ingestion` as the canonical repository for the ingestion pipeline.

2. Populate it with:

   - `src/python/projectkoios/ingestion/__init__.py` — re-exports `CodeRepositoryIngester`, `CodeRepositoryIndexer`, `ChunkIndexWriter`
   - `src/python/projectkoios/ingestion/code_repository_ingester.py` — the ingester class
   - `src/python/projectkoios/ingestion/code_repository_indexer.py` — the indexer class
   - `src/python/projectkoios/ingestion/protocols.py` — the `ChunkIndexWriter` protocol
   - `tests/test__CodeRepositoryIngester.py` — four tests covering chunk production, source path, source kind, and language preservation

3. Use PEP 420 namespace packages so that `projectkoios.ingestion` resolves correctly alongside other `projectkoios.*` subpackages from other repos. The `pyproject.toml` uses `namespaces = true` in `[tool.setuptools.packages.find]`.

4. The repo does NOT include `src/python/projectkoios/__init__.py` (namespace root is implicit).

## Package boundary

| In scope | Out of scope |
|---|---|
| `CodeRepositoryIngester` | Chunking algorithms (`projectkoios.chunking` in mothership) |
| `CodeRepositoryIndexer` | Repository loading (`projectkoios.repositories.code` in mothership) |
| `ChunkIndexWriter` protocol | Search indices (`projectkoios.indexing.InMemoryChunkIndex` in mothership) |
| Coordination of loader → chunker → index writer | Domain-specific workflow logic |

## Dependencies

- **Runtime**: requires `projectkoios` (mothership) installed as editable for `projectkoios.chunking` and `projectkoios.repositories.code`
- **Test**: pytest (tmp_path fixture for filesystem isolation)

No other Project Koios repos depend on `projectkoios-ingestion` yet. The mothership's `projectkoios.indexing` package no longer imports from ingestion; it retained only `InMemoryChunkIndex`.

## Rationale

Extracting ingestion first de-risks the namespace-package approach with a stable, well-tested module. The ingestion code had no circular dependencies, no runtime coupling to other mothership packages, and clear input/output boundaries (repository → chunks → index).

## Consequences

- `projectkoios-ingestion` is the canonical source for `from projectkoios.ingestion import ...`
- Changes to ingestion no longer require touching the mothership repo (and vice versa)
- The extraction rule from ADR20260626 is now demonstrated in practice: one component extracted, shared code stays in mothership

## Next steps

- Extract `projectkoios.search` from mothership to `projectkoios-search`
- Extract `projectkoios.api` from mothership to `projectkoios-api`
- Add ingestion tests for `CodeRepositoryIndexer` (currently has no dedicated tests)
