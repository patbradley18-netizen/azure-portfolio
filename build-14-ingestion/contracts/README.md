# Contracts

One YAML per file family. The validator (Event Grid-triggered Function) matches a dropped file against `file_pattern`, then checks header, rows and values. A file that passes is copied nowhere; its message goes on the `ingest-load` queue and the loader does the work. A file that fails is copied to `quarantine/<name>` with `<name>.reason.txt` beside it, and the ledger says why. A file whose SHA-256 is already in the ledger is a duplicate: no message, one ledger row, outcome `duplicate`.
