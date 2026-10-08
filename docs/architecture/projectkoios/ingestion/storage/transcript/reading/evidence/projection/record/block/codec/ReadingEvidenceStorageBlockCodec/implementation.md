# `ReadingEvidenceStorageBlockCodec` implementation

Encoding stores the exact block kind, structured producer evidence, typed detail, and derived block identity. Reconstruction resolves producer references by semantic identity, invokes canonical block constructors, and rejects wrong producer roles, absent references, unknown fields, or changed derived identity.
