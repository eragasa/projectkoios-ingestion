# `projectkoios.ingestion.artifact.managed` implementation

## Ownership

This clean hierarchy owns the smallest shared boundary needed when large PDF/PNG bytes remain outside MongoDB. Every package initializer is a docstring-only marker with no child re-exports.

- `ManagedArtifactMediaType` is a closed supported media vocabulary.
- `ManagedArtifactReference` identifies exact bytes by derived identity, SHA-256, byte count, and media type without a locator.
- `ManagedArtifactReferenceInventory` is the semantic bounded reference collection.
- `ManagedArtifactVerificationRequest` requests exact reference coverage without payload bytes.
- `ManagedArtifactVerificationActionizer` is the effectful resolver/verifier port implemented by concrete providers.
- `ManagedArtifactVerificationEvidence` records observed digest, length, signature/type, and verifier identity without retaining bytes.
- `ManagedArtifactVerificationEvidenceInventory` proves exact one-to-one request coverage.
- `ManagedArtifactVerificationResult` binds request, evidence, outcome, aggregate bytes, and result identity.
- `ManagedArtifactLimits` owns all pre-hash, per-artifact, count, and aggregate streaming ceilings.

## Verification lifecycle

A concrete verifier resolves an artifact identity using an explicitly configured provider, streams no more than the request bound through SHA-256/length/signature checks, releases payload buffers, and returns backend-neutral immutable observations. The provider may be content-addressed disk or object storage; provider configuration never enters artifact or page-projection semantic identity.

A reference or successful verification does not establish ownership, rights, scientific acceptance, publication, or indefinite availability. Workflow owns retries and multi-request orchestration.
