# `ReadingEvidenceStorageRecordCodec` implementation

This thin semantic composition owner delegates decomposition to `ReadingEvidenceStorageRecordGraphEncoder` and strict reconstruction to `ReadingEvidenceStorageRecordGraphDecoder`. Focused block and header codecs own their payload schemas. The composition emits a small document header, page/block members, independently retained producer/reference/limitation members, and exact typed references; reconstruction invokes public domain constructors and compares stored identities.
