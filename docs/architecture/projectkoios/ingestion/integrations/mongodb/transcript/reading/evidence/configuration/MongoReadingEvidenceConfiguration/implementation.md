# `MongoReadingEvidenceConfiguration` implementation

Frozen adapter configuration composes one backend-neutral physical mapping with a positive bounded MongoDB cursor batch size and bounded scope-index name. It owns the exact supported compound-key definition and rejects same-key provider definitions carrying unsupported options such as partial, sparse, hidden, unique, expiring, or collation behavior. Its identity binds the mapping, batch size, and index name and contains no connection string or credentials.
