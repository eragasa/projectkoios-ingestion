# `projectkoios.ingestion.artifact.managed` schematic

```text
ManagedArtifactReferenceInventory
 identity + SHA-256 + bytes + media type
                 |
                 v
ManagedArtifactVerificationRequest
                 |
                 v
concrete ManagedArtifactVerificationActionizer
 resolve + bounded streaming digest/length/signature verification
 payload bytes released
                 |
                 v
ManagedArtifactVerificationResult
 + ManagedArtifactVerificationEvidenceInventory
                 |
                 v
pure ingestion projection
```

MongoDB stores references and verification identities, never PDF/PNG payloads.
