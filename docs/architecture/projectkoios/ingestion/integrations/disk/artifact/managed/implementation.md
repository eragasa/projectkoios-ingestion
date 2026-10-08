# `projectkoios.ingestion.integrations.disk.artifact.managed` implementation

`DiskManagedArtifactBinding` maps one exact managed-artifact identity to one canonical root-relative path. `DiskManagedArtifactBindingInventory` requires deterministic unique identity and path bindings. `DiskManagedArtifactByteProvider` enforces one configured authority, resolves only explicit bindings, opens every path component descriptor-relatively with no-follow flags, accepts regular files only, enforces exact byte and chunk bounds, and translates operating-system failures into neutral typed verification errors.

The adapter never changes `ManagedArtifactReference`, returns a locator, retains payload bytes, or infers rights. Root and binding configuration do not participate in artifact or page-projection semantic identities.
