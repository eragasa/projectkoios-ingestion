# Table-structure schematic

```text
TableStructureRequest
├── exact TableDetectionResult
└── TableStructureConfiguration
             │
             ▼
DeterministicTableStructureReconstructor
             │
             ├── TableColumnDerivation
             ├── TableRegionDerivation
             │   └── TableCellDerivation
             ├── TableContinuationDerivation
             └── TableStructureDerivation
                         │
                         ▼
             TableStructureResult.from_derivations
             ├── TableStructureValidation
             │   ├── TableColumnValidation
             │   ├── TableRowValidation
             │   ├── TableCellValidation
             │   └── TableContinuationValidation
             └── TableStructure
                 ├── TableColumn
                 ├── TableRow
                 ├── TableCell
                 └── TableContinuation
```

All outputs remain deterministic proposals rather than accepted or corrected
table content.
