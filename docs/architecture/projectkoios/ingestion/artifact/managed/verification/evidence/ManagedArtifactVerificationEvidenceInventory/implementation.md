# `ManagedArtifactVerificationEvidenceInventory` implementation

The frozen semantic inventory is constructed against one exact `ManagedArtifactReferenceInventory`. Evidence must be exact, sorted, unique, within limits, and match every requested reference one-to-one with no missing, extra, or stale member. The inventory records the reference-inventory identity and aggregate observed bytes, streams ordered evidence identities through a collection digest, and derives its identity from those bounded aggregate values.
