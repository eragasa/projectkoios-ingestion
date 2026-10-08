# `projectkoios.ingestion.artifact.managed` implementation

## Ownership

This clean hierarchy owns the smallest shared boundary needed when large PDF/PNG bytes remain outside MongoDB. Every package initializer is a docstring-only marker with no child re-exports.

- `ManagedArtifactMediaType` is a closed supported media vocabulary.
- `ManagedArtifactReference` identifies exact bytes by derived identity, SHA-256, byte count, and media type without a locator.
- `ManagedArtifactReferenceInventory` is the semantic bounded reference collection.
- `ManagedArtifactVerificationRequest` binds exact reference coverage, provider implementation, authority, and streaming bounds without payload bytes.
- `ManagedArtifactByteProvider` is the effectful backend-neutral port that resolves locator-free identities into bounded transient chunks.
- `ManagedArtifactVerificationActionizer` owns provider-independent digest, length, signature, aggregate, and exact-coverage verification.
- `ManagedArtifactVerificationEvidence` records observed digest, length, signature/type, provider identity, and verifier identity without retaining bytes.
- `ManagedArtifactVerificationEvidenceInventory` proves exact one-to-one request coverage.
- `ManagedArtifactVerificationResult` binds request, evidence, outcome, aggregate bytes, and result identity.
- `ManagedArtifactLimits` owns all pre-hash, per-artifact, count, and aggregate streaming ceilings.

## Verification lifecycle

The actionizer asks an explicitly configured provider for bounded chunks, streams those chunks through SHA-256, length, signature, and aggregate checks, releases payload buffers, and returns backend-neutral immutable observations. Providers own only resolution, authorization enforcement, bounded byte access, and provider-error translation. The first concrete provider uses an explicit disk identity-to-relative-path binding inventory and descriptor-relative no-follow opens. Provider configuration never enters artifact or page-projection semantic identity.

A reference or successful verification does not establish ownership, rights, scientific acceptance, publication, or indefinite availability. Workflow owns retries and multi-request orchestration.
