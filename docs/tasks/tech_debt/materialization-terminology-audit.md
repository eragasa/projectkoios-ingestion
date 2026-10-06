# Materialization terminology audit

## Status

This audit records the repository behavior that justified the constrained
`Materializer` framework. It does **not** authorize a mass rename or migration.
Only the MongoDB extraction projection currently implements that framework.

## Definitions

- **Materializer**: an effectful action that applies a complete immutable
  projection to an explicit target under explicit authority and returns typed
  outcome evidence.
- **Create-once publisher**: an effectful owner of authoritative or retained
  artifacts. Publication is not renamed to materialization because it has
  authority, retention, and conflict semantics beyond projection application.
- **Pure assembly/linking helper**: an in-memory deterministic constructor. The
  historical verb `materialize` does not make it an effectful Materializer.
- **Operational state store**: mutable cache/checkpoint/state behavior rather
  than projection materialization.

## Classification

| Area | Current behavior | Classification | Framework action |
| --- | --- | --- | --- |
| MongoDB extraction projection | Applies canonical `ExtractionReadModel` documents to five collections with create-once conflict checks | Effectful Materializer | Conforms through `MongoExtractionProjectionMaterializer` |
| Extraction projector-to-Mongo composition | Pure projection followed by one effectful materializer | Typed synchronous Pipeline | Implemented as `ExtractionProjectionMaterializationPipeline` |
| Article structure `_materialize` | Constructs nodes, links parents/children, and creates warnings in memory | Pure assembly/linking helper | Do not make a Materializer |
| Figure detection `_materialize_warnings` | Creates warning values and links warning IDs in memory | Pure assembly/linking helper | Do not make a Materializer |
| Equation detection `_materialize_warnings` | Creates warning values from resolved candidate references | Pure assembly/linking helper | Do not make a Materializer |
| Table detection `_materialize_warnings` | Creates warning values from provisional candidates | Pure assembly/linking helper | Do not make a Materializer |
| Historical table-structure materialization records | Represented deterministic reconstructed values; current production source no longer exposes a materialization class | Pure value/assembly terminology | No framework migration |
| Disk extraction journal | Publishes checksummed authoritative payloads and chain records create-once | Create-once publisher | Keep publication boundary distinct |
| Filesystem extraction cache | Retains exact extraction cache artifacts create-once | Create-once cache publisher | Do not relabel without a separate cache audit |
| Corpus and transcript-batch filesystem writes | Publish bounded plans, transcripts, manifests, and audit artifacts | Create-once publisher | Candidate for a later publication contract, not this Materializer pilot |
| OCR/Tesseract retained outputs and workspaces | Invokes an external processor and retains bounded artifacts | Processor adapter plus create-once publisher | Keep outside projection materialization |
| Pix2Tex temporary files | Supports one external invocation and discards/retains invocation evidence according to its closed policy | Processor adapter | Keep outside projection materialization |
| SQLite processing-state store | Mutates resumable operational state | Operational state store | Never treat as projection materialization |
| Query-only projection inventory | Hashes complete canonical stored documents without changing them | ProjectorInventory plus inventory reader | Keep separate from Materializer and equivalence verification |
| Index creation | Establishes adapter readiness | Readiness operation | Keep separate from projected data effects |

## Proven common contract

The MongoDB pilot establishes the common contract now encoded under
`projectkoios.ingestion.base.materializer`:

1. one complete immutable projection value;
2. one globally explicit target identity;
3. one complete physical materialization configuration;
4. one explicit authority identity;
5. stable request and authority-neutral idempotency identities;
6. exact typed outcome evidence;
7. no projection, inventory query, retry, selection, publication, or workflow
   orchestration inside the Materializer.

The action hierarchy is:

```text
DataObjectActionizer
└── ConfigurableDataObjectActionizer
    ├── Projector
    ├── Materializer
    ├── Inventory
    │   └── ProjectorInventory
    └── Pipeline
```

A Pipeline joins two or more actionizers into one synchronous prototask for a
Workflow. Workflow continues to own CPN state, scheduling, claims, retries,
approvals, durable checkpoints, child batches, and stop propagation.

## Remaining debt

- Rename private pure `_materialize*` helpers only when touching their owning
  modules for substantive reasons; a terminology-only refactor is not useful.
- Audit transcript-batch and corpus publishers separately before defining any
  generic Publisher framework.
- Keep the current Materializer generic narrow until a second genuinely
  effectful projection application proves the same contract.
