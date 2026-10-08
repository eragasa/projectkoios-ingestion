# `MongoReadingEvidenceSourceActionizer` implementation

Composes `MongoReadingEvidenceReadModelReader` with pure `ReadingEvidenceReadModelVerifier`. The action method performs no Mongo-specific canonical reconstruction and returns only backend-neutral `ReadingEvidenceSourceResult`.
