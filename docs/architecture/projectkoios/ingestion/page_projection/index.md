# `projectkoios.ingestion.page_projection`

This public module owns validation and typed loading of reading-scale page
projections. It binds explicit document metadata to owner validation evidence
and exposes only citation-aligned paragraph, heading, and owner-validated
figure-caption text to downstream consumers.

It does not own Search plans, indexing, database publication, directory
discovery, equation acceptance, or media retrieval.
