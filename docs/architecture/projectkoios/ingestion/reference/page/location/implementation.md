# Reference page-location implementation

## Problem

`reference_locator.py` combines resource bounds, failures, Unicode tokenization,
anchor identity, two records, cross-record lineage verification, locator
construction, and matching in one root module. Locator construction and matching
are synchronous operations without immutable Base requests/actionizers.

## Design

The semantic owner is `projectkoios.ingestion.reference.page.location`.
Package initializers are docstring-only and consumers import defining leaves.
Two action boundaries preserve the existing two-stage behavior:

```text
ReferencePageLocatorProjectionRequest
    -> ReferencePageLocatorProjectionActionizer
    -> ReferencePageLocator

ReferencePageLocationRequest
    -> ReferencePageLocationActionizer
    -> ReferencePageLocatorResult
```

Projection verifies reusable reference evidence, exact clean-transcript lineage,
one page index, and a `ReferenceTopicAnchorInventory`. Matching re-verifies the
exact page, asks the inventory to partition its anchors by whole-token phrase
matching, and emits semantic identity inventories and byte counts without page
or anchor payloads.

The hierarchy does not use stateless utility classes as namespaces for helper
functions. `ReferenceTopicAnchor` and its inventories are immutable domain
values that own normalization and matching. `ReferencePageEvidenceVerifier`
binds one evidence record and transcript as instance state. Locator and result
identity derivations are bounded immutable values in `identity.py`. Closed
limitations have a semantic immutable owner in `limitation.py`. Identity grammar
belongs directly to the bounded derivations in `identity.py`; page-index bounds
belong to the request and derivations that consume them. No procedural
validation-helper module remains. Every public path into tokenization and
identity hashing enforces its own resource bounds.

## Compatibility and authority

Stable locator/result identities, Unicode NFKC plus case-fold tokenization,
whole-token phrase behavior, contract/processor versions, bounds, limitations,
and field order remain unchanged. Python imports receive a clean break: the old
module and ingestion-root exports are deleted without aliases.

Neither action infers claim support, citation acceptance, human proofreading,
publication suitability, or scientific validity. Workflow retains retries,
approvals, and orchestration.

## Validation

Required evidence includes exact historical locator/result and downstream claim
candidate identity replay, focused action and bound tests, action-contract and
hierarchy smell gates, Ruff, mypy, full pytest, Sphinx, package builds, and
clean-wheel absence checks for the old module and exports.
