# Clean transcript module size

## Status

Deferred maintainability debt. This is not a known correctness defect or an
unused subsystem.

## Context

`src/python/projectkoios/ingestion/clean_transcript.py` contains 2,050 lines.
It owns the canonical `CleanTranscript` result, its evidence records and
configuration, the deterministic projector, and projection policy. The module
currently includes:

- a 291-line `CleanTranscript` result class;
- a 311-line `DeterministicCleanTranscriptProjector` with a 284-line action;
- a 600-line stateless `CleanTranscriptContract` whose behavior is live even
  though the class itself has no external consumer.

This subsystem is actively used by transcript batching, offline verification,
derivation audit, reference-evidence projection, page location, and transcript
evidence selection. Its published clean transcript and reference-evidence
contracts cross repository boundaries. Earlier prototype clean-transcript
families were already collapsed into this canonical family.

## Desired reduction

The eventual semantic owner is `projectkoios.ingestion.transcript.clean` (not
`trainscript/clean`). It should be a package decomposed by record, projection,
policy, and concrete wire-boundary ownership rather than a move of all 2,050
lines into `transcript/clean.py`.

Reduce the amount of code and review surface only when behavior can be deleted,
generalized at its true owner, or made materially simpler. Preserve
`CleanTranscript` as the canonical result and keep projection, validation,
audit, publication, and downstream evidence responsibilities explicit.

Any future change must preserve:

- stable clean-transcript identities and canonical serialized bytes;
- exact raw text, source spans, page and block order, and typed exclusions;
- dehyphenation, page-number, publisher-front-matter, and private-use-glyph
  evidence;
- the `automated_unreviewed` status and all non-acceptance limitations;
- transcript-batch create-once publication and replay;
- derivation-audit behavior and reference-evidence compatibility;
- downstream References, Search, and Workflow contract compatibility.

Do not split the file merely to redistribute the same code. Do not introduce a
compatibility facade, generic validation graph, stateless utility owner, or
parallel clean-transcript model. Removing `CleanTranscriptContract` is useful
only if its behavior moves to concrete owners with a net reduction in code and
complexity.

## Revisit condition

Revisit this debt when clean-transcript behavior must change, when a concrete
owner can absorb and simplify existing policy, or when review evidence shows a
specific duplicated or unnecessary invariant. Do not schedule a standalone
move-only refactor solely to reduce per-file line count.

## Completion evidence

Completion requires a material net reduction rather than a file-count change.
Required evidence includes focused behavioral tests, the full test suite, Ruff,
mypy, clean-wheel inspection, unchanged transcript and reference-evidence
golden bytes, deterministic transcript-batch replay, and downstream consumer
conformance.
