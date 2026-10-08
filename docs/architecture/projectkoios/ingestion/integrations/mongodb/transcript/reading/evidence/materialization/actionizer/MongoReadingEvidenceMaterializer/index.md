# `MongoReadingEvidenceMaterializer`

Effectful idempotent action writing immutable generation-scoped records in bounded create-once dependency-ordered batches, reconstructing and verifying the result, and publishing one immutable completion manifest last. It uses no generation-wide transaction and owns no Workflow lifecycle.
