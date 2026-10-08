# `ReadingEvidenceStorageProjector` implementation

Pure projector validates one complete reconciled canonical projection, emits bounded child records, independently observes the canonical inventory, computes per-collection completion evidence, emits the completion member, and returns one complete read model. It accepts no backend capability or authority.
