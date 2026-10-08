# `ManagedArtifactVerificationResult` implementation

The frozen successful result binds the exact request, complete evidence inventory, verifier implementation, and derived result identity. It validates matching reference-inventory identity, exact aggregate bytes, request bounds, provider implementation, and verifier implementation. Verification failure raises a typed error and cannot create a partial result.
