# Code smell review

Apply this review to every maintained hierarchy or contract change. The review
is owner-facing: code and tooling conform to the owner's domain semantics, not
the reverse. Findings in the changed scope are fixed before merge rather than
recorded as compatibility waivers.

## Automated checks

The local smoke suite checks objective rules in each migrated source scope:

- every registered migrated scope exists and contains Python source;
- semantic words are not flattened into underscore-named modules or package
  directories;
- a package does not contain a redundant same-named module such as `x/x.py`;
- package initializers contain only their ownership docstring and do not
  re-export implementation names;
- every concrete `DataObjectModel` or `AbstractImmutableDataObject`, including
  indirect subclasses, is defined as a frozen dataclass; and
- every registered actionized operation has an immutable request, concrete
  Ingestion Base actionizer, and immutable Ingestion Base result, with exact
  `action(*, request)` typing and no registered legacy analyzer/processor route
  or hidden actionizer configuration.

When an operation adopts the request/actionizer/result standard, add it to the
smoke suite's `_ACTIONIZED_OPERATIONS` registry in the same change. Registration
is deliberately incremental: it does not misclassify explicitly unmigrated
processor boundaries as already actionized.

Hosted clean-wheel CI additionally verifies that its registered removed modules
and package exports are absent and that its registered defining leaves import
from the built wheel. The reviewed old-to-new path map remains the human-owned
inventory that determines those registrations.

Leading underscores used only for module privacy are not semantic separators.
Private compound stems still require the same semantic review.

## Human semantic review

Automated token splitting is prohibited. For every moved or introduced path,
review the owned type or operation and answer these questions:

- Does the path represent semantic ownership rather than filename token order?
- Is the leaf the real role (`model`, `actionizer`, `backend`, `definition`,
  `error`, `status`) rather than a repeated or adjectival name?
- Is a broad or catch-all module hiding independently owned concerns?
- Does unstable API compatibility introduce an alias, re-export facade, legacy
  decoder, stale field, awkward class name, or stale stable-ID namespace?
- Does each synchronous domain operation expose one complete immutable request,
  one Ingestion Base actionizer, and one immutable result rather than an
  analyzer/processor method with positional inputs or hidden configuration?
- Does a DataObject contract require multiple inheritance or create a diamond
  merely to classify one request or result?
- Is every immutable concrete record actually implemented as a frozen
  dataclass?
- Are identity, evidence, or configuration concepts introduced only where the
  owning action requires them?
- Does a pipeline expose a fixed synchronous composition as one workflow
  prototask, without concealing topology, retries, leases, approvals,
  checkpoints, concurrency, or stop propagation?
- Does an owner-specific concept leak into a generic base contract?

A hierarchy change is ready only when its PR includes the exact old-to-new path
map, the semantic reason for every non-obvious leaf, action-registry enrollment
when applicable, direct-import and wheel inventory evidence, and no unresolved
finding in its scope.
