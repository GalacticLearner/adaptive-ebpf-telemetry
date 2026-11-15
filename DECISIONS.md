# Decisions

- **D001 (2026-10-30):** Preserve the three supplied sources byte-for-byte in `context/`. The v3/v4 reviews and ZIP are unavailable. The plan's conservative empirical research boundary is authoritative until the missing sources can be reconciled.
- **D002 (supersedes initial host assumption):** The project was built and run on Ubuntu 26.04 LTS x86-64. The saved experiment host is kernel `7.0.0-31-generic`; a privileged known-count eBPF smoke passed, and Linux calibration/pilot attempts are preserved. No kernel, boot, or security policy changes are required for reproduction.
- **D003:** C owns the timing-sensitive agent, lifecycle, detector, supervisor and workload. Python owns scheduling, manifests, validation and inference. A Python reference controller is a diagnostic oracle tested against C, never the primary collector.
- **D004:** Use no cross-study baseline reuse by default. Extra matched NONE trials increase the conservative matrix estimate and avoid invalid pairing. Every study owns complete blocks; attribution and stats-on remain separate.
- **D005:** Maps and links are unpinned, owned by one per-trial child. The controller receives target TIDs and a start timestamp only; schedule, truth, application counters and drift labels are not passed to it.
- **D006:** JSON Schemas are closed objects; unresolved discovery/calibration values may exist in drafts but freeze rejects them. Fixed modes still run the same detector.
- **D007 (2026-11-15):** Use sealed Linux run records as the source of truth for the report. The saved four-block pilot is fixed NONE versus FIX_Q01 only; keep all noise warnings and do not infer an adaptive-policy benefit from it.
