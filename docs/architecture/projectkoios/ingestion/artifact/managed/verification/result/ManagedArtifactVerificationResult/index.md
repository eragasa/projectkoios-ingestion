# `ManagedArtifactVerificationResult`

Immutable successful action result binding the exact request to complete verification evidence, verifier identity/version, aggregate observed bytes, and deterministic result identity without retaining payload bytes. Failures use `ManagedArtifactVerificationError` rather than a partial result.

See the [implementation](implementation.md) and [schematic](schematic.md).
