# `DiskManagedArtifactBindingInventory` implementation

The semantic collection accepts exact bindings in artifact-identity order, enforces the global managed-artifact count ceiling, and rejects duplicate artifact identities or relative paths. `require` fails closed when an identity has no configured locator.
