# `projectkoios.ingestion.artifact.managed` schematic

```text
ManagedArtifactReferenceInventory
 identity + SHA-256 + bytes + media type
                 |
                 v
ManagedArtifactVerificationRequest
                 |
                 v
ManagedArtifactVerificationActionizer
                 |
                 v
ManagedArtifactByteProvider
 resolve + bounded transient chunks
                 |
                 v
provider-neutral digest/length/signature/coverage verification
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
