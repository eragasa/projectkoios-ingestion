# `reference.evidence.source`

## Owner

`ReferenceEvidenceSource` owns one immutable source-byte identity: blob ID,
hash algorithm, content SHA-256, byte length, and media type.

## Invariants

Only `sha256` is supported; the blob ID must equal
`blob:sha256:<content_sha256>`; the digest is canonical lowercase SHA-256; byte
length is non-negative; and text is non-empty, bounded valid UTF-8.

This record contains no filename, source locator, private path, machine
location, credentials, protected content, or publication authority.
