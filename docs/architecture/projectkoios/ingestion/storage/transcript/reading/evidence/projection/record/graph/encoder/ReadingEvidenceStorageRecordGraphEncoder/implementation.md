# `ReadingEvidenceStorageRecordGraphEncoder` implementation

The encoder emits one document header, every page and block, every exactly retained producer, every managed reference, and every limitation. It detects conflicting producer identities, enforces configured count/byte bounds through storage-document construction, and returns canonical collection/document order.
