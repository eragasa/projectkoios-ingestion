# `MongoReadingEvidenceReadModelReader` implementation

Requires exactly one current completion member first, decodes its neutral manifest only to obtain exact counts, bounds all collection reads, canonicalizes observed BSON-compatible objects, reconstructs neutral storage documents, rejects missing/extra/duplicate scope, and returns one read model. It does not reconstruct canonical reading domain values.
