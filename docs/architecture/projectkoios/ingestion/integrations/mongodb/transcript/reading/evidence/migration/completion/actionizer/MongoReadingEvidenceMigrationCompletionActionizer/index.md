# `MongoReadingEvidenceMigrationCompletionActionizer`

Effectful conditional create-once action that re-observes both source and target inventories, verifies neither drifted from the successful migration verification result, and publishes the immutable target completion manifest. Any drift or existing conflict fails closed.
