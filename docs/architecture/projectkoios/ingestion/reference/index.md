# `projectkoios.ingestion.reference`

This package is the semantic owner for ingestion-produced evidence about
reference sources and their deterministic processing lineage.

[`evidence`](evidence/index.md) owns the Proposed reference-evidence record and
its reversible JSON boundary. [`page`](page/index.md) owns payload-free page
navigation evidence, and [`claim`](claim/index.md) owns payload-free claim
candidate projection.

This package does not own canonical-reference acceptance, asset attachment,
claim support, manuscript use, Search indexing, rights clearance, or
publication authority. Those decisions remain with their existing repositories
and human authorities.
