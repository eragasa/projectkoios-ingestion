# `ingestion.transcript.batch` implementation

The target source layout replaces the flat `transcript_batch.py`,
`transcript_plan_cli.py`, and `transcript_batch_cli.py` modules with an owned
package:

```text
transcript/
  __init__.py          # namespace only
  batch/
    __init__.py        # namespace only
    contracts.py
    planning.py
    execution.py
    plan_cli.py
    compose_cli.py
```

Package initializers re-export nothing. Internal and command-entry-point imports
name the defining module directly. Existing console-script names may remain
stable while their import targets move.

`contracts.py` owns immutable identified plan data and validation errors.
`planning.py` owns bounded inventory resolution, exact predecessor identities,
strict serialization, and durable create-once plan publication. `execution.py`
owns the existing deterministic composition order, explicit concrete renderer
injection, derivation audit, and private immutable output publication. It must
not import reusable behavior from a CLI module; extraction execution moves
behind a non-CLI owner or an injected `SourceExtractor` before this package
migration. CLI modules only parse arguments, call one owning function, and map
typed failures to exit status.

This package split is behavior-preserving. It does not alter transcript content,
selection policy, detector thresholds, source identities, output names,
permissions, no-follow protections, or publication races. It also does not
make native-text extraction OCR-complete or make automated equation proposals
eligible for chunk text.

## Migration sequence

1. Land and validate the bounded Simon extraction correction first.
2. Move transcript-batch contracts without changing serialized identities.
3. Move planning/resolution and verify durable-plan byte replay.
4. Move execution/publication and verify exact output replay and race tests.
5. Retarget the two existing console scripts to their defining CLI modules.
6. Remove flat modules only after repository imports, tests, source/wheel build,
   and clean-wheel command smoke all pass.

This second migration is intentionally sequenced after the PDF owner fix so it
cannot obscure Simon page-80 or chunk-008 evidence.
