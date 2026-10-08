# `reference.evidence.identity`

`identity.py` owns bounded reference-evidence record-ID derivation. Every scalar,
semantic inventory, nested record, completeness invariant, and complete-lineage
relationship is validated before the historical identity material is hashed.
The derivation canonically serializes the unchanged historical identity input,
requires it to fit the identity-input ceiling owned by
`ReferenceEvidenceLimits`, and only then fingerprints those same bytes with
`SHA256Fingerprinter`. The derivation formats the established
`reference-evidence-record:sha256:` identity directly; no procedural identity
helper reserializes the material. This bounds hash work without changing the
accepted identity algorithm or digest.
