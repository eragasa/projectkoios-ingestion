# `scripts.equation_enrichment` schematic

```mermaid
flowchart LR
    CLI["repository CLI"]
    Workflow["vendor-neutral equation-recognition workflow"]
    Abstract["AbstractEquationRecognizer"]
    Pix2Tex["Pix2Tex adapter"]
    Request["EquationRecognitionRequest"]
    Result["EquationRecognitionArtifact"]
    CPN["non-authoritative CPN shadow"]

    CLI --> Workflow
    CLI --> Pix2Tex
    Workflow --> Request
    Workflow --> Abstract
    Pix2Tex --> Abstract
    Abstract --> Result
    Result --> Workflow
    Workflow -. shadowed by .-> CPN
```

The CLI selects concrete adapters. The workflow depends only on the
vendor-neutral abstraction. The CPN depends on the workflow and never defines
its authority.
