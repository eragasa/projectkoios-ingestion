# `ReadingEvidenceReadModelReader` implementation

Abstract effectful port declares bounded retrieval for an exact target, generation, document, current schema, and read authority. Implementations return a complete `ReadingEvidenceReadModel` or a typed backend-neutral read failure; they do not reconstruct canonical domain values.
