# `reference.evidence.json`

This package is the sole reversible typed JSON boundary for
`ReferenceEvidenceRecord`. It separates boundary orchestration from each nested
wire-object schema:

- [`contract`](contract/index.md) — bounded parser/serializer composition, canonical replay, and domain error translation.
- [`record`](record/index.md) — aggregate record wire object.
- [`artifact`](artifact/index.md) — bound-artifact wire object.
- [`source`](source/index.md) — source-identity wire object.
- [`extraction`](extraction/index.md) — extraction-evidence wire object.
- [`transcript`](transcript/index.md) — transcript-evidence wire object.
- [`audit`](audit/index.md) — audit wire object.
- [`layer`](layer/index.md) — nested audited-layer-count wire object.
- [`value`](value/index.md) — strict shared field access over closed `JsonValue` trees.

The package initializer is docstring-only. No package re-export or legacy
parse/serialize function is provided.

The wire profile remains UTF-8 compact sorted JSON without a terminal newline.
Duplicate keys, non-RFC constants, malformed UTF-8/JSON, unknown or missing
fields, unsupported enum/version values, noncanonical bytes, inconsistent
identities, incomplete lineage, and resource-limit violations fail closed.
