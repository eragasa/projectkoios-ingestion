# `reference.evidence.artifact`

## Owner

`ReferenceEvidenceArtifact` owns the immutable media type, lowercase SHA-256
digest, and byte length of one bound producer artifact.

## Behavior

`from_bytes()` rejects non-bytes and content above the artifact ceiling before
fingerprinting through `SHA256Fingerprinter`. `verify()` checks exact byte
length and digest and raises the domain verification error on mismatch.
Construction validates the media type, canonical digest, non-negative size,
and artifact bound through `ReferenceEvidenceValueValidator` and evidence
limits.

This leaf does not parse JSON, read files, infer an artifact locator, or grant
trust in the artifact's semantics.
