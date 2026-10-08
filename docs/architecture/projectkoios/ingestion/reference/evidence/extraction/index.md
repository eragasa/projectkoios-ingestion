# `reference.evidence.extraction`

## Owner

`ReferenceEvidenceExtraction` owns the extraction subset of one reference
evidence record: exact artifact identity, extraction contract version,
manifest/document identities, status, extractor name/version, configuration
digest, and warning count.

## Invariants

The artifact media type and extraction contract version are fixed to the
supported production values. Status must be `IngestionStatus`; identities and
producer strings are non-empty bounded UTF-8; warning count is non-negative.
Completion requirements across extraction, transcript, and audit remain owned
by the aggregate record.
