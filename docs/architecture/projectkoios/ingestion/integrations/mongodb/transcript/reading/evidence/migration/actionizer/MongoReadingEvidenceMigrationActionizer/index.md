# `MongoReadingEvidenceMigrationActionizer`

Effectful bounded action that reads one exact source batch, applies every typed adjacent migration step in memory, writes immutable create-once target-generation records, and returns batch evidence. Workflow owns batch iteration, retries, checkpoints, stop propagation, and cutover.
