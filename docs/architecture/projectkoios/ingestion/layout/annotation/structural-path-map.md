# Layout annotation structural path map

The model-resolution and human-final-review contracts are new provisional
contracts. No previous path, compatibility façade, alias, or legacy decoder is
retained.

| Defining path | Ownership |
|---|---|
| `layout/annotation/kind.py` | Evidence-author-neutral annotation outcomes and failure kinds |
| `layout/annotation/region.py` | Corrected region geometry and native-block membership |
| `layout/annotation/order.py` | Corrected reading-order edge and bounded graph validation |
| `layout/annotation/failure.py` | Explicit affected-evidence failure annotation |
| `layout/annotation/validation.py` | Shared case/reference/outcome validation for human and model evidence |
| `layout/annotation/collection.py` | Complete human-authored annotation evidence |
| `layout/annotation/model/resource.py` | Provider-neutral model/runtime resource identity |
| `layout/annotation/model/prompt.py` | Exact prompt, manifest, and response-schema lineage |
| `layout/annotation/model/configuration.py` | Sampling and response-size bounds |
| `layout/annotation/model/request.py` | One exact replica invocation request |
| `layout/annotation/model/actionizer.py` | Runtime-neutral model invocation port |
| `layout/annotation/model/invocation.py` | Exact canonical request document, raw response, and failure evidence |
| `layout/annotation/model/candidate.py` | Structurally valid model-authored candidate |
| `layout/annotation/model/limitation.py` | Explicit unusable/unresolved evidence limitation |
| `layout/annotation/model/parsing/request.py` | One exact invocation parsing request |
| `layout/annotation/model/parsing/derivation.py` | Shared pure strict response interpretation and schema decoding |
| `layout/annotation/model/parsing/status.py` | Closed parsed/rejected outcome vocabulary |
| `layout/annotation/model/parsing/actionizer.py` | Strict bounded response parsing operation |
| `layout/annotation/model/parsing/result.py` | Reconstructed parsed candidate or parsing limitation |
| `layout/annotation/model/resolution/policy.py` | Replication and agreement requirements |
| `layout/annotation/model/resolution/request.py` | Exact complete replica set |
| `layout/annotation/model/resolution/actionizer.py` | Pure non-conflicting agreement admission |
| `layout/annotation/model/resolution/result.py` | Admitted or unresolved model-resolution evidence |
| `layout/annotation/human/evidence.py` | Explicit optional terminal human review state |

All package initializers are docstring-only ownership markers. Consumers import
directly from defining leaves.
