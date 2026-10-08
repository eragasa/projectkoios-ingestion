# Managed-artifact foundation reduction path map

| Previous committed path | Reduced defining leaf |
|---|---|
| `media.py` | `media/type.py` |
| `reference.py::ManagedArtifactReference` | `reference.py` |
| `reference.py::ManagedArtifactReferenceInventory` | `inventory.py` |
| managed verification operation | `verification/request.py`, `verification/actionizer.py`, `verification/result.py` |
| managed verification observations | `verification/evidence.py` |
| managed provider boundary | `verification/provider.py`, `verification/error.py` |

Replacement package initializers are docstring-only ownership markers. Consumers import defining leaves directly; no compatibility façade remains. Physical disk binding and resolution are defined under `integrations.disk.artifact.managed`, not this neutral hierarchy.
