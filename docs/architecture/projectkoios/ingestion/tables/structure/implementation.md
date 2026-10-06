# Table-structure implementation

Each configuration, request, column, row, cell, continuation, and result class
lives in a direct noun module; the package-owned `TableStructure` record lives
in `model.py` to avoid `structure/structure.py`. Qualified derivation, validation,
status, role, record, specification, limits, and reconstructor definitions live
under semantic ownership packages and direct role leaves. Immutable objects inherit
`AbstractTableStructureDataObject`, which specializes the ingestion
immutable-data base and owns their shared bounded-value invariants. Derivation
records additionally inherit `AbstractDerivation`; validation records inherit
`AbstractValidation`. Request and result additionally implement the Project
Koios action-family bases. The package initializer is a namespace marker and
re-exports nothing.

Deterministic intermediate state is represented by immutable
`TableColumnDerivation`, `TableRegionDerivation`, `TableCellDerivation`,
`TableContinuationDerivation`, and `TableStructureDerivation` objects.
`TableStructureResult.from_derivations` creates canonical warnings and links
their identities to the final cells and structures. `TableColumnValidation`,
`TableRowValidation`, `TableCellValidation`, and
`TableContinuationValidation` retain successful validation records under the
orchestration of `TableStructureValidation`. Identity derivation and component-specific validation are owned by the affected
domain classes. There are no module-level helper functions,
stateless utility classes, or underscore-prefixed helper modules.
`TableSourceRecord` and `TableStructureWarningSpecification` give remaining
internal values nominal immutable owners. The refactor preserves contract
versions, stable identity inputs, serialized fields, processing bounds, warning
semantics, and proposal-only status.

Consumers import concrete classes from their defining leaves. Package
initializers are docstring-only ownership markers. No compatibility request
alias, root-package export, or monolithic facade is retained. The complete
reviewed inventory is the [structural path map](structural-path-map.md).
