# SQLite processing-state integration

`SqliteProcessingStateStore` is the concrete local SQLite adapter for
`AbstractProcessingStateStore`. It owns all SQLite connections, pragmas,
statements, cursors, rows, schema migration, and transaction handling.
