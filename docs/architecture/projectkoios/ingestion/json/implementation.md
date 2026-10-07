# `projectkoios.ingestion.json` implementation

## Target layout

```text
json/
  __init__.py
  value.py
  parser.py
  serializer.py
  contract.py
  canonical.py
  error.py
  limits/
    __init__.py
    definition.py
    error.py
```

Every package initializer is a docstring-only ownership marker. Consumers
import direct defining leaves.

## Dependency direction

`value` and `limits` are leaves. `parser` and `serializer` depend on them and on
shared JSON errors. `contract` composes one parser, one serializer, and typed
record/value conversion hooks. `canonical` is a one-way deterministic
serializer, not a JSON contract, because arbitrary source types are not
reconstructable from its JSON tree.

The package imports no PDF, OCR, transcript, reference, storage, integration,
or Workflow module. Domain-specific JSON contracts depend inward on this
package, never the reverse.

## `JsonContract[T]`

A `JsonContract[T]` names one complete typed JSON boundary. It owns:

- conversion from `T` to a closed `JsonValue`;
- reconstruction of `T` from a parsed `JsonValue`;
- one explicit serializer configuration;
- one explicit parser/limit configuration;
- UTF-8 text and byte entry points; and
- optional canonical replay verification.

It does not own the invariants of `T`; construction of the record remains the
authoritative invariant check. It does not infer Workflow lifecycle, authority,
acceptance, evidence, or publication permission.

Concrete domain contracts are named precisely, for example
`PdfBatchPlanJsonContract`, `SelectiveOCRPlanJsonContract`, and
`ReferenceEvidenceJsonContract`. A generic record is never called merely a
“contract” because it happens to be JSON serializable.

## Error translation

Shared machinery raises typed JSON parse, serialization, and limit failures.
Existing domain boundaries may translate those failures to established domain
errors. Migration must retain exact public messages wherever they are currently
part of tested behavior.

The generic package must not import domain errors or accept arbitrary error
classes in configuration. Translation occurs in the concrete domain contract.

## Bounded processing

All untrusted JSON is bounded before recursive standard-library parsing:

1. validate input type;
2. encode or decode strict UTF-8;
3. reject input above the configured byte ceiling;
4. scan lexical container depth and balance;
5. parse with duplicate-key, constant, integer, and float hooks;
6. traverse the parsed tree once to enforce node, depth, string, and numeric
   bounds; and
7. pass the closed `JsonValue` to the concrete record decoder.

Serialization projects values iteratively or with an explicit depth bound,
rejects cycles and unsupported values, and enforces the configured output-byte
limit before returning content. Generic serializers and reversible contracts
require finite floats. The one-way canonical compatibility profile alone
retains historical non-finite bytes used by internal malformed-geometry
identity evidence. External values must be bounded before canonical bytes are
supplied to stable-ID hashing.

## Formatting and replay

`JsonSerializer` has no implicit repository-wide formatting default. A concrete
contract selects every byte-affecting option:

- key sorting;
- non-finite-number policy;
- indentation;
- separators;
- ASCII escaping;
- terminal newline; and
- maximum UTF-8 output bytes.

Migration acceptance compares exact pre- and post-migration bytes for each
existing durable family. A canonical contract may additionally parse,
reconstruct, reserialize, and require byte equality.

## Migration sequence

1. Land and review this repository-wide JSON architecture before changing PDF
   batch source.
2. Capture representative and boundary replay fixtures for every durable JSON
   family in the inventory.
3. Implement `value`, `limits`, `error`, `parser`, `serializer`, `contract`, and
   `canonical` with focused adversarial tests.
4. Move generic JSON responsibilities out of root `identity.py` and
   `serialization.py` without changing stable IDs or canonical bytes.
5. Use the PDF batch plan as the first domain-specific `JsonContract`
   specialization while splitting its item and plan records.
6. Migrate OCR, reconciliation, transcript, reference, page-projection, cache,
   and journal families separately; each requires its own replay evidence and
   review.
7. Reduce integration-private strict parsers only when the shared parser can
   preserve their resource and typed-failure behavior.
8. Delete old helpers only after all production consumers use direct defining
   leaves and clean-wheel validation passes.

## Non-goals

This architecture does not:

- make every `json.dumps()` call a contract;
- unify CLI presentation with durable records;
- move domain field schemas into the generic JSON package;
- weaken domain-specific validation or errors;
- silently canonicalize established pretty formats;
- add metadata, identity, evidence, or authority to records; or
- migrate every JSON boundary in one pull request.
