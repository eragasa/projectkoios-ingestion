# MongoDB reading-evidence index-readiness implementation

Index readiness is separate from document materialization. It creates a deterministic named compound index over schema, generation, evidence-document, and storage-document identities for every configured physical collection. Existing named definitions must match exactly.

The source reader fails closed before document queries when any configured index is absent or different. Workflow owns when this separately authorized action runs.
