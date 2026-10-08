# `ReadingEvidenceEquivalenceVerifier` implementation

The verifier compares full canonical document values, independently observed inventories, and projection-result identities. For same-store replay it additionally requires baseline and replay materializations to bind the same projection, target, configuration, and document count. Every replay collection must report zero creations and an unchanged count equal to that collection's complete baseline created-plus-unchanged count. It performs no I/O and grants no lifecycle authorization.
