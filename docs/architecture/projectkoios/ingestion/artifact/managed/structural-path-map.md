# Managed-artifact foundation reduction path map

| Previous committed path | Reduced defining leaf |
|---|---|
| `media.py` | `media/type.py` |
| `reference.py::ManagedArtifactReference` | `reference.py` |
| `reference.py::ManagedArtifactReferenceInventory` | `inventory.py` |

Replacement package initializers are docstring-only ownership markers. Consumers import defining leaves directly; no compatibility façade remains.
