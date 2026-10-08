# `reference.evidence.verification.request`

## Owner

`ReferenceEvidenceVerificationRequest` is one frozen `DataObjectActionRequest`
containing a `ReferenceEvidenceRecord`, expected source SHA-256, byte length,
media type, and optional extraction, clean-transcript, and derivation-audit
artifact bytes.

Construction validates exact types, canonical source digest, bounded text and
non-negative size, and bounds every supplied artifact before verification. It
adds no inferred identity, configuration, authority, or lifecycle state.
