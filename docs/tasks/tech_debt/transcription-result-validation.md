# Transcription result validation size

## Status

Deferred maintainability debt. This is not a known correctness defect.

## Context

PR #29 replaced the former 2,441-line `transcription.py` monolith with focused
owner modules and removed the graph of subordinate validation classes. The
result is a substantial improvement in ownership, navigation, and reviewability.

The remaining localized debt is
`src/python/projectkoios/ingestion/transcription/result_validation.py`, which
contains 461 lines, including a 359-line
`TranscriptionResultValidation.validate()` method. That implementation was
reduced from 564 lines, but its remaining trust-boundary checks are still tiring
to review and modify safely. Recording this residual debt does not negate the
much larger reduction achieved by PR #29.

Further work was deliberately stopped after attempts to split the method made
the file larger without reducing behavior. Moving the same checks into more
classes, modules, helpers, or phases would disguise rather than repay this debt.

## Desired reduction

Reduce the amount of validation code by deleting duplication or unnecessary
policy, not by redistributing the same logic. Preserve one result-boundary
validation owner and the existing separation between validation and producer
derivation.

Any future reduction must preserve:

- canonical result and validation identities;
- item, omission, warning, source, and page relationships;
- exact source-span validation;
- ordering, coverage, and configured resource limits;
- compact validation evidence without retaining complete subject graphs;
- unchanged golden request, result, cache, and serialized identities.

Do not introduce subordinate validator classes, compatibility facades, free or
private helper functions, static utility methods, local imports, or
`TYPE_CHECKING` escapes. Do not rerun the composer or reproduce complete source
derivations merely to validate their output.

## Completion evidence

This debt is complete only when the file and principal validation operation are
materially smaller because behavior was removed or generalized at its true
owner. Required evidence includes focused behavioral tests, the full test
suite, Ruff, mypy, structural and import-cycle scans, clean-wheel inspection,
and unchanged structured-transcription golden identities and serialized bytes.
