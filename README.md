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
optionally, one raw text artifact per physical page. Existing artifacts are
never overwritten. A handled publication error removes files and directories
created by that invocation; because filesystems do not provide a portable
multi-file transaction, a process or machine crash can leave a partial set that
must be inspected and removed before retrying.

```bash
koios-ingest-pdf article.pdf \
  --source-id reference:example2020 \
  --output .koios/example2020/extraction.json \
  --raw-text-directory .koios/example2020/pages
```

PDF parsing runs in the CLI process and reads the complete source into memory.
PyMuPDF is a complex native parser, not a security sandbox. Applications that
accept untrusted PDFs should enforce input and resource limits and use an
operating-system isolation boundary when their threat model requires one.

Routing and role split live in `projectkoios-bootstrap/docs/agent-charter.md`.
