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
  indirect subclasses, is defined as a frozen dataclass;
- registered private-member-clean scopes define no underscore-prefixed member
  functions;
- registered private-import-clean scopes do not import underscore-prefixed
  members across module boundaries;
- registered utility-clean scopes do not use `staticmethod` or `classmethod` to
  turn classes into procedural namespaces; cohesive codecs and legacy scopes
  remain outside that registry until separately reduced;
- registered semantic-collection scopes expose no public raw `tuple[...]`
  fields; private tuple storage remains an implementation detail of immutable
  inventories;
- every module function has a production-source reference or an explicit entry
  in `_EXTERNAL_MODULE_FUNCTIONS`, and no conditional block is empty
  scaffolding; and
- every registered actionized operation has an immutable request, concrete
  Ingestion Base actionizer, and immutable Ingestion Base result, with exact
  `action(*, request)` typing and no registered legacy analyzer/processor route
  or hidden actionizer configuration.

When an operation adopts the request/actionizer/result standard, add it to the
smoke suite's `_ACTIONIZED_OPERATIONS` registry in the same change. Register a
public function in `_EXTERNAL_MODULE_FUNCTIONS` only when its caller genuinely
lives outside production source, and remove stale registrations. Add a domain
to `_NO_PRIVATE_MEMBER_FUNCTION_SCOPES` or
`_NO_CROSS_MODULE_PRIVATE_IMPORT_SCOPES` as soon as its applicable debt is
removed. Register reduced domains or precise leaves in
`_NO_STATIC_UTILITY_METHOD_SCOPES` and semantic collection domains in
`_NO_PUBLIC_RAW_TUPLE_FIELD_SCOPES`; file registrations must fail if the file
is missing. Registration is deliberately incremental: it does not misclassify
explicitly unmigrated processor boundaries as already actionized or turn broad
legacy helpers into public API by renaming alone.

Hosted clean-wheel CI additionally verifies that its registered removed modules
and package exports are absent and that its registered defining leaves import
from the built wheel. The reviewed old-to-new path map remains the human-owned
inventory that determines those registrations.

Leading underscores used only for module privacy are not semantic separators.
A private function must remain inside its defining module; cross-module use
requires a semantic public owner or co-location with its consumer. Private
compound stems still require the same semantic review.

## Human semantic review

Automated token splitting is prohibited. For every moved or introduced path,
review the owned type or operation and answer these questions:

- Does the path represent semantic ownership rather than filename token order?
- Is the leaf the real role (`model`, `actionizer`, `backend`, `definition`,
  `error`, `status`) rather than a repeated or adjectival name?
- Is a broad or catch-all module hiding independently owned concerns?
- Is a member function private because its responsibility lacks a semantic
  owner, and does it actually depend on the owning object?
- Is a private function imported outside its defining module, or is any
  function left without a production owner or caller?
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
- Are external identity inputs bounded and semantically validated before any
  hashing, without untyped `**values` identity bags or record-construction
  bypasses around an actionizer?
- Does a public domain field expose a raw tuple where an immutable semantic
  inventory should own ordering, uniqueness, bounds, and item meaning?
- Does a procedural `require_*` helper remain where the consuming immutable
  value, request, or derivation can own the invariant directly?
- Does a pipeline expose a fixed synchronous composition as one workflow
  prototask, without concealing topology, retries, leases, approvals,
  checkpoints, concurrency, or stop propagation?
- Does an owner-specific concept leak into a generic base contract?

A hierarchy change is ready only when its PR includes the exact old-to-new path
map, the semantic reason for every non-obvious leaf, action-registry enrollment
when applicable, direct-import and wheel inventory evidence, and no unresolved
finding in its scope.
