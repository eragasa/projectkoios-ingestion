# `ingestion.base` schematic

```text
projectkoios.base.DataObject
└── AbstractDataObject
    └── AbstractImmutableDataObject
        ├── AbstractIdentity
        │   ├── OllamaMultimodalRegionProcessorIdentity
        │   ├── OllamaMetadataResponseIdentity
        │   └── OllamaRawResponseIdentity
        ├── AbstractDerivation
        │   └── TableStructureDerivation records
        └── AbstractValidation
            └── TableStructureValidation records
```
