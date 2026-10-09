# `ReadingEvidenceProjectionMaterializationPipeline` implementation

The pipeline invokes `ReadingEvidenceStorageProjector` and then its injected `ReadingEvidenceMaterializer`. Its immutable result retains both stage-result identities and compact materialization evidence without retaining the complete projected graph.

The pipeline performs no iteration, source discovery, write freeze, retry, checkpoint, drift check, cutover, rollback, or cleanup. Workflow owns those operations and may invoke this pipeline once per frozen canonical source.
