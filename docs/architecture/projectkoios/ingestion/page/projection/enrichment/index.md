# `projectkoios.ingestion.page.projection.enrichment`

Implemented pure current-schema enrichment from one exact `PageProjectionResult`
to one immutable entry per projected block. Paragraph and heading entries expose
exact retained raw text and source provenance. Figure-caption entries remain
present with an explicit unavailable disposition because current caption
normalization does not establish an exact raw/clean pair.

This boundary contains no Search, References, bibliography, claim-support,
storage, or workflow policy.

See the [implementation](implementation.md) and [schematic](schematic.md).
