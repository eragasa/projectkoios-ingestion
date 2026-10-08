# `ReadingEvidenceIdentityDerivation`

Deterministic derivation that accepts only validated bounded semantic material, serializes it once through `CanonicalJsonSerializer`, enforces the identity-input byte ceiling, and fingerprints those exact bytes with `SHA256Fingerprinter`.
