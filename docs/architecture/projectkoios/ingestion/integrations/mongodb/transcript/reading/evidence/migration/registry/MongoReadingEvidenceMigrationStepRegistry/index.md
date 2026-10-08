# `MongoReadingEvidenceMigrationStepRegistry`

Immutable explicit registry mapping each supported adjacent source/target schema pair and transformer identity to one typed transformation implementation. Missing, duplicate, skipped, or ambiguous steps fail before reads or writes.
