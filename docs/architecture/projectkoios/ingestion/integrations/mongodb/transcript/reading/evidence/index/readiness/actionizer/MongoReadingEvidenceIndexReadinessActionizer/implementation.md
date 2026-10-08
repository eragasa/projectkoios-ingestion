# `MongoReadingEvidenceIndexReadinessActionizer` implementation

The action validates the injected database capability against the request target, inspects every configured collection, creates only absent indexes, rejects conflicting named definitions, and returns exact created/unchanged counts. Provider failures become typed MongoDB reading-evidence errors.
