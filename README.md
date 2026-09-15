# projectkoios-ingestion

Source ingestion and document processing pipeline for Project Koios.

This package coordinates source loaders, document processors, chunk producers,
and index writers through destination-independent interfaces. It does not own
search storage, bibliography management, Markdown projection, or vault writes.

- [Architecture](docs/architecture.md)
- [Public data contracts](docs/contracts.md)
- [PDF document ingestion ADR](docs/adr.pdf-document-ingestion.md)
- [Document-processing task status](docs/tasks/document-processing-backlog.md)
- [Redistributable PDF fixture matrix](tests/fixtures/pdf/README.md)

The optional deterministic PDF adapter is installed with `.[pdf]` and exposed
through `koios-ingest-pdf`. It writes a versioned extraction contract and,
optionally, one raw text artifact per physical page. `--cache-root` enables the
filesystem extraction cache: a compatible hit returns the exact cached result
without invoking PDF extraction, and a miss is cached before artifacts are
published. Existing artifacts are never overwritten. A handled publication
error removes files and directories created by that invocation; because
filesystems do not provide a portable multi-file transaction, a process or
machine crash can leave a partial artifact set that must be inspected and
removed before retrying.

```bash
koios-ingest-pdf article.pdf \
  --source-id reference:example2020 \
  --cache-root .koios/extraction-cache \
  --output .koios/example2020/extraction.json \
  --raw-text-directory .koios/example2020/pages
```

Cache entries use canonical JSON envelopes at
`CACHE_ROOT/v1/<key-prefix>/<sha256(cache-key)>.json`. Key identity covers the
cache format, extraction contract, logical and exact blob source identities,
extractor and installed backend versions, and extraction-affecting
configuration. Envelopes record source, processor, configuration, manifest,
and payload identities for diagnosis. The diagnostic source locator is not a
key field under the accepted source contract, so a hit preserves the locator
recorded by the cached extraction. Malformed or excessively nested JSON,
invalid Unicode, truncated data, unrepresentable numeric values, unsupported
versions, and identity inconsistency are reported as corruption; none is treated
as an ordinary miss. Invalid keys or results supplied to `put` raise
`ValueError` before cache-root mutation.

Each cache write flushes an exclusive same-directory temporary file, atomically
publishes it only when the destination is absent, and syncs the directory. An
existing valid entry for the exact key is accepted; an unrelated or corrupt
regular file is preserved and reported instead of being overwritten.
Concurrent writers therefore accept the first complete valid entry. Uncatchable
termination can leave an ignored temporary, and a filesystem that does not
honor durable sync can lose the newest publication.

This cache backend requires POSIX descriptor-relative filesystem operations,
`O_DIRECTORY`, `O_NOFOLLOW`, `O_NONBLOCK`, and no-follow `stat` and hard-link
support. It fails
closed with `ExtractionCacheSafetyError` before touching the cache root when
those capabilities are unavailable; uncached extraction remains portable. The
cache does not provide eviction, migration, distributed locking, automatic
corruption repair, or cache-root symlink support.

PDF parsing runs in the CLI process and reads the complete source into memory.
PyMuPDF is a complex native parser, not a security sandbox. Applications that
accept untrusted PDFs should enforce input and resource limits and use an
operating-system isolation boundary when their threat model requires one.

Routing and role split live in `projectkoios-bootstrap/docs/agent-charter.md`.
