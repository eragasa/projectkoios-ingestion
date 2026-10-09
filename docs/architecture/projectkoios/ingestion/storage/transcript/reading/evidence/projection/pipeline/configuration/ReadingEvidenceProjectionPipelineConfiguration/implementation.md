# `ReadingEvidenceProjectionPipelineConfiguration` implementation

Construction derives a stable identity from both stage-configuration identities. Validation requires their exact current schema versions to match, preventing a pipeline from projecting one schema and materializing another.
