# `ManagedArtifactVerificationActionizer`

Concrete effectful action `ManagedArtifactVerificationRequest -> ManagedArtifactVerificationResult`. It consumes bounded transient provider chunks, verifies digest, length, media signature, aggregate bounds, and exact coverage, then releases payload bytes and returns backend-neutral evidence.

See the [implementation](implementation.md) and [schematic](schematic.md).
