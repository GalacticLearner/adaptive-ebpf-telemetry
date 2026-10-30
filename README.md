# Adaptive eBPF Telemetry

A reproducible study implementation comparing **GATE** (keep syscall probes attached and sample at entry) with **SWITCH** (change detail link attachment), with a common scheduler sentinel, three collection modes and a calibration-based soft application-overhead target.

Implementation lives in this main folder. The supplied plan and assignment are preserved under `context/`; originals remain in `research/`.

**Current status:** portable implementation checks pass. The development host is Windows without WSL, so no real BPF load, workload calibration, benchmark campaign or empirical claim is complete. Consult [phase progress](PROGRESS.md), [issues](ISSUES.md) and [next action](NEXT.md). Synthetic data is explicitly labeled and kept under `data/synthetic/`.

## Start here

- [Linux setup, smoke and reproduction](artifact/REPRODUCE.md)
- [Calibration and freeze procedure](artifact/CALIBRATION.md)
- [Assignment traceability](requirements_traceability.md)
- [Methods/report and evidence ledger](paper/manuscript.md)
- [Research claim boundary](research/claims.md)

```bash
python -m runner --help
python -m runner estimate-matrix --study all
python -m runner test --unprivileged
python -m runner status
```

Install exact Python dependencies from `requirements.lock` (analysis/figures additionally use `requirements-analysis.lock`). Linux builds use C, Clang BPF v3, libbpf1.5.1, bpftool and target BTF. `make build` generates real target headers/skeletons. `make test` runs portable checks; `make test-privileged` requires a capable authorized Linux host. No default command launches the multi-day campaign.

## Components

`src/bpf/` contains scheduler bins and paired raw-syscall collection. `src/agent/` owns loading, nonblocking link transitions, epoll/timerfd/signalfd, ring consumption and a bounded binary sink. `src/workloads/` generates CPU/tmpfs work and independent incident truth. `runner/` owns host diagnostics, immutable attempts, readiness, cgroups, randomization, retries, freeze and packaging. `analysis/` validates records and computes paired block-level inference. Configuration is closed/schema-checked; unresolved calibration values block freeze.

The primary registry is 56 cells/672 trials at default 12 blocks (~54.1 nominal host-hours). The full conservative registry includes supplementary controls, attribution and secondary-host subsets; `estimate-matrix` reports counts/runtime/storage. No adaptive advantage or overhead guarantee follows from the design alone.
