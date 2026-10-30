# Requirement → implementation → acceptance evidence

| Assignment / plan requirement | Module | Verification and planned artifact |
|---|---|---|
| Three collection intensities, common event definitions | `src/bpf/detail.bpf.c`, `src/agent/main.c`, `src/common/wire.h` | Entry sampling branches and ABI tests; real known-count test; P3/P4 kernel gates pending |
| Always-on low-cost signal | `src/bpf/sentinel.bpf.c` | Old/new/wrap/idle/retention tests and concurrent two-snapshot reader; sentinel cost attribution pending |
| Trigger, recovery hysteresis, dwell, sensor gaps | `src/common/policy.c`, `runner/reference.py` | C/reference replay at25/100/500ms; gap/recovery/override tests; actual transition integration pending |
| Explicit budget and model error | `runner/calibration.py`, C supervisor, `analysis/stats.py` | Calibration-only context UCLs; matched phase-level effects; no hard budget claim |
| CPU and cached IO workloads, fixed inputs, checksums | `src/workloads/workload.c` | Linux cross compilation, selftest, per-worker counters; actual repeatability and perturbation pending |
| Short futex bursts, independent truth, unseen CPU incident | `src/workloads/workload.c`, `runner/matrix.py` | Deterministic jitter schedules, actual timing/call ledgers; real generation tests pending |
| Drift and low/high background, identical seeds | `runner/matrix.py`, `runner/trial.py` | 56 core cells,672 trials, paired schedules; drift phases analyzed separately |
| GATE/SWITCH boundaries and lifecycle | C agent, Python lifecycle oracle | Attach exit→entry ordering,rollback,queued re-escalation,20ms drain; real race/quiescence tests pending |
| Event loss, pairing and cleanup | C counters/sink, `analysis/validate.py` | Nonoverlapping ledgers,CRC/truncation/clock rejection,immutable seals; exact kernel truth pending |
| No observer truth access | C agent runtime input contract | Runtime includes only TIDs,frozen sensor/controller parameters; no schedule/work counters supplied |
| Fixed curve, trigger-only, ablations and robustness | `runner/matrix.py` | Complete study registry with matched controls and full estimates; all real cells unexecuted |
| Confidence intervals,independent repetitions | `analysis/stats.py`, `analysis/pipeline.py` | Whole-block bootstrap,paired log-ratio effect,one-sided compliance,Holm utility,Poisson count interval |
| Required plots/raw tables/report | `analysis/figures.py`, `runner/report.py` | Checksummed inputs,PDF/SVG/PNG,CSV/evidence ledger; empirical figures blocked by absent data |
| Environment locks and reproducibility | `artifact/`, Makefile, runner CLI | Pinned dependencies,source hashes,doctor,freeze,attempt archives,package/read-back; real replay pending |
| Literature / at least five relevant sources | `paper/references.bib`, `research/evidence_access.csv` | Five primary-source records; unresolved full-text audits explicitly preserved |
| Autonomous progress and honest phase gates | `PROGRESS.md`, `state/progress.json`, `ISSUES.md`, `NEXT.md` | All52 original step IDs retained; blocked gates never marked passed by synthetic work |
