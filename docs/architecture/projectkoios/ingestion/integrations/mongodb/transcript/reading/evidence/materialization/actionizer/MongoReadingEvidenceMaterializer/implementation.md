# `MongoReadingEvidenceMaterializer` implementation

Concrete neutral materializer port. It verifies configured target/capability/configuration identities, parses only already-canonical projected JSON, checks exact BSON size, writes non-completion members before completion, and uses `_id` plus full observed equality for create-once exact replay. Index readiness remains a separate authorized action.
