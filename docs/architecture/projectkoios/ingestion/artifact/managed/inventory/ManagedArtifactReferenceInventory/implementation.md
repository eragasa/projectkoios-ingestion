# `ManagedArtifactReferenceInventory` implementation

The frozen semantic inventory accepts exact `ManagedArtifactReference` values only in ascending artifact-identity order. It rejects duplicates and global count or aggregate-byte overflow before streaming the complete ordered artifact identity sequence through a collection digest and deriving `inventory_id` from that bounded aggregate identity. Iteration and `require` expose references without exposing mutable storage.
