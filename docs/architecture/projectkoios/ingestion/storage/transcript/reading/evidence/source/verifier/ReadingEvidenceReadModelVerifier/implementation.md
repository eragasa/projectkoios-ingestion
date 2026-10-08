# `ReadingEvidenceReadModelVerifier` implementation

Pure verifier requires current schema and one valid completion member, recomputes all member and collection evidence, strictly decodes child payloads, reconstructs the canonical document, independently observes its inventory, and compares every expected identity. Failure is typed and contains no provider value.
