# `reference.evidence.error`

## Owner

This leaf owns:

- `ReferenceEvidenceError`, the domain `ValueError` base;
- `ReferenceEvidenceParseError`, for malformed, noncanonical, or invalid wire documents; and
- `ReferenceEvidenceVerificationError`, for unusable evidence or byte-identity mismatch.

`ReferenceEvidenceLimitError` belongs separately to `limits/error.py` and
inherits the domain base. JSON machinery remains backend-neutral and is
translated into these errors only at the concrete reference-evidence boundary.
