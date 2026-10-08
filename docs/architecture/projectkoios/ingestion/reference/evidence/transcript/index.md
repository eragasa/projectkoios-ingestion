# `reference.evidence.transcript`

## Owner

`ReferenceEvidenceTranscript` owns exact clean-transcript artifact identity,
result/status, structured-transcription identity, ordered layout identities,
text digest/length, producer name/version/configuration, and warning count.

## Invariants

The clean-transcript artifact media type is fixed. Layout identities use the
non-empty, bounded, unique semantic inventory in `layout.py`; order is
preserved. Text identity is a canonical SHA-256 and lengths/counts are
non-negative. Aggregate complete status and audit coverage belong to
`lineage.py`.
