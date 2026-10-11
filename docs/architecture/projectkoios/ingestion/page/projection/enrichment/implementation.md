# Page-projection evidence enrichment implementation

## Boundary

`PageProjectionEvidenceEnrichmentRequest` accepts one exact fresh
`PageProjectionResult`. `PageProjectionEvidenceEnrichmentActionizer` performs a
pure deterministic derivation and returns
`PageProjectionEvidenceEnrichmentResult`. The result reconstructs the complete
entry inventory and rejects changed, missing, extra, or reordered entries.

Every projected block produces exactly one entry keyed by the same canonical
source evidence identity that Search exposes as
`PageProjectionChunk.source_evidence_id`. Each entry also binds the exact page
projection result, reading source result, reading projection result, managed
artifact verification result, source, document, source page, page location,
projected page, and projected block identities.

## Available text enrichment

Version `1.0` admits only paragraph and heading blocks. It retains:

- raw source text joined in the same declared source-record order and with the
  same newline boundary used by the canonical clean-text block;
- a SHA-256 digest derived from the exact retained UTF-8 text;
- the closed `text_block_raw_source_sequence` basis;
- source-record, source-block, producer, and producer-version bindings;
- ordered unique source-span identities;
- exact opaque producer warning identities and graph-visible affected
  identities;
- `detail_status=unavailable` and no synthetic warning detail when the current
  producer retains only an opaque warning identity; and
- exact applicable reading-limitation identities, closed codes, and typed
  affected identities.

The output does not copy clean indexed text because the exact projected block is
already bound by identity. It does not translate warnings into Search-owned
warning semantics.

## Explicitly unavailable captions

Figure captions are projected from normalized unique association text. Current
reading evidence does not define a non-arbitrary exact raw/clean pair when one
caption binds one or more associations. Version `1.0` therefore emits
`PageProjectionEvidenceUnavailable` with
`figure_caption_has_no_exact_raw_clean_pair`, the exact caption join key,
producer-record identity, cross-bindings, and applicable limitations. It does
not choose an association by sorted identity, invent retained text, or silently
omit the caption key.

## Ownership and exclusions

The enrichment package is an Ingestion-owned sanitized observation. Downstream
composition may join it with a Search page-projection chunk by exact source
evidence identity. Search need not and must not dereference `CleanTranscript`,
`ReadingEvidenceDocument`, `ReadingEvidenceSourceResult`, or their object
graphs.

The package does not construct `EvidenceItem`, attach a bibliographic work or
source asset, promote candidate identity, select a citekey, decide rights,
infer claim support, rank evidence, serialize a wire artifact, perform I/O, or
publish a corpus. Those concerns remain with their current owners.
