# Decisions

- **D001 (2026-10-30):** Preserve the three supplied sources byte-for-byte in `context/`. The v3/v4 reviews and ZIP are unavailable. The plan's conservative empirical research boundary is authoritative until the missing sources can be reconciled.
- **D002:** Windows is the available development host; WSL reports not installed. Implement Linux sources and verify portable components here. No simulated kernel pass or benchmark evidence is acceptable. Do not install WSL, change kernel/security policy, or create remote infrastructure implicitly.
- **D003:** C owns the timing-sensitive agent, lifecycle, detector, supervisor and workload. Python owns scheduling, manifests, validation and inference. A Python reference controller is a diagnostic oracle tested against C, never the primary collector.
- **D004:** Use no cross-study baseline reuse by default. Extra matched NONE trials increase the conservative matrix estimate and avoid invalid pairing. Every study owns complete blocks; attribution and stats-on remain separate.
- **D005:** Maps and links are unpinned, owned by one per-trial child. The controller receives target TIDs and a start timestamp only; schedule, truth, application counters and drift labels are not passed to it.
- **D006:** JSON Schemas are closed objects; unresolved discovery/calibration values may exist in drafts but freeze rejects them. Fixed modes still run the same detector.
