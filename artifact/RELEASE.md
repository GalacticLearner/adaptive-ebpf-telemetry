# Local release

The checksummed source/data bundle and its file-by-file manifest are generated under `artifact/releases/`. The filename identifies the source commit. Packaging reads the tarball back and checks every member against its SHA-256 before reporting success.

The release includes the tracked implementation/protocol/sources/progress,methods manuscript and evidence records,plus a fresh synthetic raw/analysis/figure replay under `data/synthetic/release-verification/`. It contains no real kernel or application measurement. A release manifest records the actual source commit,dirty status,file inventory and archive checksum.

Preserved coursework/research sources are for this local handoff; public redistribution is not authorized by this task. Python/OS dependency binaries are not bundled. Reinstall the pinned packages and rebuild with the target Linux toolchain as documented in `REPRODUCE.md`.

Original plan status and pending volume are in `STATUS.md` and `state/status_summary.json`. Eight development compiler checks pass. The final portable suite has35passed checks and two explicitly blocked native executions on Windows. The full Linux phase gates remain pending.
