# Next research steps

The Linux implementation and privileged known-count smoke are recorded as complete for the tested host. Do not treat the fixed 1% pilot as a completed adaptive-policy comparison.

1. Review the external-CPU noise warning present in all 16 pilot attempts; decide whether to retain the run as exploratory evidence (the current report does) and collect a clean-host sensitivity pilot if appropriate.
2. Complete/verify calibration for event-rate/storage peaks, workload work units, normal detector training and validation, mode/action cost bounds, and precision-based block count.
3. Freeze a resolved protocol and source/configuration hashes.
4. Run paired NONE, SENT, fixed LOW/MEDIUM/HIGH, ADAPT_GATE, and ADAPT_SWITCH comparisons across the configured workload/background/drift matrix.
5. Analyze all valid and invalid attempts together, preserving noise flags, event-loss ledgers, uncertainty, and negative outcomes.

See `artifact/CALIBRATION.md` and `artifact/REPRODUCE.md` for the concrete staged commands. Planned matrix size and runtime are estimates, not completed experimental results.
