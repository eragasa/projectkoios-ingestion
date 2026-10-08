# `ReadingEvidenceReadModel` implementation

Frozen aggregate requires canonical member ordering, unique logical `(collection, document_id)` keys, one scope, one current schema, one completion member, and a bounded count. Its aggregate digest covers every member's full canonical digest; its identity also binds source projection and configuration identities.
