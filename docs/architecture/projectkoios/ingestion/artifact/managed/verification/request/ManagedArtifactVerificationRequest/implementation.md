# `ManagedArtifactVerificationRequest` implementation

The frozen request binds one exact reference inventory to provider implementation and authority identities plus positive per-artifact, aggregate, and stream-chunk bounds. Every bound is capped by `ManagedArtifactLimits`; requested bounds must cover all referenced lengths before `request_id` is derived. It carries no bytes, locator, credentials, or provider object.
