# Table-structure implementation

Each configuration, request, column, row, cell, continuation, structure,
result, status, role, error, derivation, validation, materialization, and
reconstructor class lives in its own named module. Immutable objects inherit
`AbstractTableStructureDataObject`, which specializes the ingestion
immutable-data base and owns their shared bounded-value invariants. Request and
result additionally implement the Project Koios action-family bases. The
package initializer is a namespace marker and re-exports nothing.

Deterministic intermediate state is represented by immutable
`TableColumnDerivation`, `TableRegionDerivation`, `TableCellDerivation`,
`TableContinuationDerivation`, and `TableStructureDerivation` objects.
`TableStructureMaterialization` represents warning publication and linked final
structures. `TableColumnValidation`, `TableRowValidation`,
`TableCellValidation`, and `TableContinuationValidation` retain successful
phase evidence under the orchestration of `TableStructureValidation`. Identity
derivation and component-specific validation are owned by
the affected domain classes. There are no module-level helper functions,
stateless utility classes, or underscore-prefixed helper modules.
`TableSourceRecord` and `TableStructureWarningSpecification` give remaining
internal values nominal immutable owners. The refactor preserves contract
versions, stable identity inputs, serialized fields, processing bounds, warning
semantics, and proposal-only status.

Consumers import concrete classes from their owning modules. No compatibility
request alias, root-package export, or monolithic facade is retained.
