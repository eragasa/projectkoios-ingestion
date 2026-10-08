# Reference page-location structural path map

| Old owner | New owner |
| --- | --- |
| contract and processor identifiers | `reference/page/location/definition.py` |
| `reference_locator.py` limits | `reference/page/location/limits/definition.py` |
| `ReferenceLocatorLimitError` | `reference/page/location/limits/error.py` |
| other locator errors | `reference/page/location/error.py` |
| `ReferencePageLocatorStatus` | `reference/page/location/status.py` |
| tokenization and one anchor value | `reference/page/location/anchor.py` |
| anchor and anchor-identity collections | `reference/page/location/inventory.py` |
| locator/result identity derivation and identity grammar | `reference/page/location/identity.py` |
| fixed result limitations | `reference/page/location/limitation.py` |
| page-index request bound | `reference/page/location/projection/request.py` |
| procedural `reference/page/location/validation.py` | deleted; no helper facade |
| state-bound record/transcript page verification | `reference/page/location/verification.py` |
| `ReferencePageLocator` | `reference/page/location/locator.py` |
| `ReferencePageLocatorResult` | `reference/page/location/result.py` |
| `ReferencePageLocator.create()` input | `reference/page/location/projection/request.py` |
| `ReferencePageLocator.create()` operation | `reference/page/location/projection/actionizer.py` |
| `ReferencePageLocatorChecker.execute()` input | `reference/page/location/matching/request.py` |
| `ReferencePageLocatorChecker.execute()` operation | `reference/page/location/matching/actionizer.py` |
| `tests/test__ReferencePageLocator.py` | `tests/projectkoios/ingestion/reference/page/location/` |

`reference_locator.py` is deleted. No compatibility module, root export,
legacy constructor, checker alias, or free anchor-identity function remains.
Downstream claim projection imports the new result and status leaves directly.
