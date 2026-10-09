# `ReadingEvidenceProjectionPipelineRequest` implementation

The request derives an authority-neutral idempotency key from source evidence and digest, target, and configuration identities. Its request identity additionally binds the invoking authority. It contains no inferred workflow, migration, approval, or cutover state.
