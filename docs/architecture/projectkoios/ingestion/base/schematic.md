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

projectkoios.base.DataObjectActionizer
└── Projector[Source, Configuration, Projection]
    ├── fixed final action(ProjectionRequest)
    ├── stateless pure project(Source[], Configuration)
    └── ProjectionResult
```
