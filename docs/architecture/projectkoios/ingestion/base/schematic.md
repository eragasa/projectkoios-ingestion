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

base/
├── data/object.py
├── projector/
│   ├── identity/{model.py,error.py}
│   └── payload/error.py
├── materializer/identity/{model.py,error.py}
└── inventory/identity/{model.py,error.py}
```

Every package initializer in this inventory is an ownership marker. Public use
imports the defining leaf; no initializer re-exports moved names.
