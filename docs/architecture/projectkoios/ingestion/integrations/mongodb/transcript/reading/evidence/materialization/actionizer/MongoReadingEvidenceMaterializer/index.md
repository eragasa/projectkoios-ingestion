# `MongoReadingEvidenceMaterializer`

Effectful idempotent action writing already-projected immutable generation-scoped records sequentially in create-once dependency order and publishing the projected completion member last. It reports per-collection created/unchanged counts, performs no canonical reconstruction, uses no generation-wide transaction, and owns no Workflow lifecycle.
