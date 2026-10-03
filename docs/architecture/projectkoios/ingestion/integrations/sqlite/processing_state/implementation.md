# SQLite processing-state implementation

The adapter requires a private regular database file under a private real
parent directory. It enables foreign-key checks, WAL journaling, and full
synchronous durability. Database files are mode `0600`.

Initialization creates the existing `books`, `chunks`, `candidates`, and
`events` decomposition. Legacy event rows are retained and assigned stable
migration identities before a unique event-identity index is created.

Loads explicitly map SQLite rows into immutable backend-neutral records; no
`sqlite3.Row` crosses the adapter. Saves acquire an immediate transaction,
verify the expected snapshot identity, preserve immutable queue geometry,
reconcile candidate inventory, append events idempotently, and replay the
committed database into the exact requested snapshot before commit.
