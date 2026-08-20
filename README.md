# projectkoios-ingestion

Source ingestion and document processing pipeline for Project Koios.

This package coordinates source loaders, document processors, chunk producers,
and index writers through destination-independent interfaces. It does not own
search storage, bibliography management, Markdown projection, or vault writes.

- [Architecture](docs/architecture.md)
- [Public data contracts](docs/contracts.md)
- [PDF document ingestion ADR](docs/adr.pdf-document-ingestion.md)

Routing and role split live in `projectkoios-bootstrap/docs/agent-charter.md`.
