# Linux Reproduction Guide

This project and its recorded eBPF experiments were run on Linux. The preserved privileged smoke and pilot records are under `state/evidence/linux-smoke-20261114-001/` and `data/pilot/bounded-q01-4blocks-20261114-001/`.

## Recorded environment

The host inventory captured on 2026-11-14 records Ubuntu 26.04 LTS, x86-64, kernel `7.0.0-31-generic`, 20 logical CPUs, approximately 14.5 GiB RAM, cgroup v2, readable BTF, and the required scheduler/syscall tracepoints. The host's current CPU inventory identifies a 12th Gen Intel Core i7-12700H. Recorded tools: Python 3.14.4, Clang 18.1.8, GCC 15.2.0, GNU Make 4.4.1, bpftool 7.7.0, and pkg-config 2.5.1. The agent links against the project-built libbpf 1.5.1; the bpftool binary separately reports its libbpf 1.7 runtime.

The host check and passed privileged smoke are preserved in `state/host.json` and `state/evidence/linux-smoke-20261114-001/checks.json`. The smoke checked full-detail, low-detail, and sentinel-only behavior. At full sampling, 2,000 selected calls completed and were written, with no ring or sink drops.

## Repository structure

- `src/bpf/`: scheduler sentinel and raw-syscall detail programs.
- `src/agent/`, `src/common/`: libbpf agent, bounded sink, mode control, cost/policy helpers, and wire formats.
- `src/workloads/`: CPU/I/O workloads and known-count test workload.
- `runner/`: host diagnostics, calibration/pilot/campaign commands, trial lifecycle, validation and reporting.
- `analysis/`: metrics, whole-block inference, plots, and record validation.
- `configs/`: pilot, protocol, calibration, confirmatory, and robustness configurations.
- `schemas/`: strict JSON schemas.
- `data/calibration/`, `data/pilot/`: immutable run attempts and sealed raw results.
- `results/`: derived validation and analysis outputs.
- `state/`: host/toolchain lock, smoke evidence, and campaign status records.
- `paper/`, `latex_report/`: manuscript/evidence ledger and IEEE report.

## Prerequisites and setup

Use an authorized x86-64 Linux host with BTF, cgroup v2, `sched_switch`, raw syscall tracepoints, ring-buffer support, and permission to load tracing programs. Root access is used for the recorded privileged test. The host should be idle enough to keep external CPU activity below the configured noise threshold.

The exact Python pins are in `requirements.lock` and `requirements-analysis.lock`. The bootstrap script resolves and installs the Ubuntu build packages, downloads libbpf 1.5.1 and verifies its SHA-256, creates `.venv/`, builds target BTF-based skeletons, and compiles the binaries:

```bash
bash artifact/bootstrap-linux.sh
sudo .venv/bin/python -m runner doctor --output state/host.json
PKG_CONFIG_PATH="$PWD/.deps/libbpf-1.5.1/lib/pkgconfig" \
  make CLANG=clang-18 build
```

The bootstrap changes installed packages through apt but does not change the kernel, boot configuration, or security policy. Review it before execution. Preserve `state/bootstrap/apt-resolved.txt`, `dpkg-installed.txt`, and `toolchain-actual.json` as host-specific environment records.

## Configuration and modes

The primary configuration parameters are:

- `sentinel`: `sched/sched_switch`, 5 ms rotating bins, 2,048 slots, 10 ms read lag, and gap-to-LOW behavior.
- `detail`: raw `sys_enter`/`sys_exit`, syscall allowlist, 8 MiB ring, 8 MiB queue, in-flight limits, transport record version, and sampling probabilities.
- `controller`: initial mode, GATE or SWITCH mechanism, 250 ms dwell, 5% throughput budget, hysteresis, optional supervisor, and transition-cost bounds.
- `detector`: robust log1p score, score scale floor, candidate thresholds, 100 ms control period, 500 ms recovery, and independently calibrated model input.
- `workload`: CPU or I/O family, pinned workers, compute repeats, read sizes, drift point, warmup/measurement/drain periods, seed, and background settings.
- `incidents`: incident kind, duration, randomized onset jitter, spacing, timeout, and background pattern.
- `experiment`: policy set, workload/background/drift combinations, paired block count, retry limits, and host noise thresholds.
- `analysis`: paired block as the independent unit, 10,000 bootstrap draws, 95% confidence, multiplicity policy, and declared endpoint set.

LOW selects no detailed entries; MEDIUM samples 10%; HIGH selects all eligible entries. The fixed pilot policy `FIX_Q01` samples 1%, so it is a separate fixed-rate baseline, not the MEDIUM mode. Adaptive policies are `ADAPT_GATE` and `ADAPT_SWITCH`. A null calibration/model field is intentionally unresolved and prevents a valid freeze.

## Smoke test

Run the bounded known-count test after setup. Commands are shown separately because the runner and child workload both need access to tracing:

```bash
.venv/bin/python tools/configure_host.py \
  --config configs/calibration.yaml \
  --output state/calibration-host-local.yaml \
  --compute-repeats 32
sudo .venv/bin/python -m runner test --privileged \
  --config state/calibration-host-local.yaml \
  --output state/evidence/linux-smoke-local
.venv/bin/python -m runner test --unprivileged
```

The privileged smoke should verify the expected fixed count at full selection, zero selected events in LOW, and no detail output from SENT. The repository's recorded smoke passed and is retained; re-running it should use a new output directory to avoid changing that evidence.

## Calibration and experiments

Calibration precedes a confirmatory campaign. It selects a fixed CPU work unit and I/O compute batch, measures event and storage rates, estimates perturbation, fits/validates the normal sentinel model, derives mode/action costs, and chooses the paired block count. Do not tune a detector on confirmatory incident outcomes. Follow the detailed stage sequence in `artifact/CALIBRATION.md`.

The recorded four-block pilot is configured by `state/pilot-q01-4blocks-20261114.yaml`. It has two workload families, low background, no drift, a jittered 10 ms futex incident, and paired NONE/FIX_Q01 comparisons. To reproduce it without overwriting existing evidence, use a fresh path:

```bash
sudo .venv/bin/python -m runner pilot \
  --config state/pilot-q01-4blocks-20261114.yaml \
  --study primary --limit 16 \
  --output data/pilot/reproduction-q01
```

For a complete study, first resolve the required fields in a separate execution config, run `estimate-matrix`, and freeze the protocol. Then run one campaign at a time:

```bash
.venv/bin/python -m runner estimate-matrix \
  --config state/final-draft.yaml --study all \
  --output state/final-matrix.json
.venv/bin/python -m runner freeze \
  --config state/final-draft.yaml --output state/freeze.json
sudo .venv/bin/python -m runner run \
  --config /path/to/frozen-execution.yaml --study primary \
  --output data/confirmatory/campaign-001
```

The planned primary design is 56 policy/workload/background/drift cells and 672 trials at 12 paired blocks. This is a protocol estimate, not the number of completed experiments. Do not launch the full matrix until the calibration, storage, and freeze gates are satisfied.

## Validate and analyze saved results

The following commands operate on the recorded pilot data and write new analysis output:

```bash
.venv/bin/python -m runner validate \
  --input data/pilot/bounded-q01-4blocks-20261114-001 \
  --output state/validation-pilot-rerun.json
.venv/bin/python -m runner analyze \
  --input data/pilot/bounded-q01-4blocks-20261114-001 \
  --output results/pilot-rerun --figures
.venv/bin/python -m runner report \
  --input results/pilot-rerun --output paper/pilot-rerun
```

Each attempt has a manifest, resolved configuration, intended schedule, ground-truth ledger, event counters, noise flags, validation record, and `seal.json`. The seal hashes the attempt inventory. Do not hand-edit attempts or replace noise flags. Invalid attempts and valid-but-noisy attempts remain visible in the analysis.

## Results and metrics

The recorded pilot analysis is in `results/pilot/bounded-q01-4blocks-20261114-001/`; its raw attempts are under `data/pilot/bounded-q01-4blocks-20261114-001/`. It contains four paired blocks per workload and compares only NONE with FIX_Q01. Observed paired throughput-loss estimates were 1.85% (CPU) and 11.21% (I/O); capture was 1.17% and 1.00%, respectively; on-time alert recall was zero for both. All 16 attempts were valid and had the external-CPU noise warning. With four blocks, the runner treats the declared 5% budget classification as inconclusive.

The per-attempt `counters.json` distinguishes eligible/selected/rejected calls, completion, ring reservation failures, emitted/consumed/written records, sink drops, abandoned calls, and undrained events. `resources.csv` has process and host samples. `results.json` and `effects.csv` contain paired effects and uncertainty; `run_metrics.json` has per-trial metrics. These values have distinct denominators and should not be merged into a single event-loss number.

## Troubleshooting and reproducibility notes

- **BPF load/permission errors:** run `doctor`, verify root or equivalent tracing privileges, readable `/sys/kernel/btf/vmlinux`, cgroup v2, and the required tracepoints. Do not relax system security settings to force a pass.
- **Missing compiler or BPF backend:** install through the authorized Ubuntu bootstrap and build with `CLANG=clang-18`; use the project-built libbpf pkg-config path when linking the agent.
- **Smoke output already exists:** choose a new output directory; attempts are immutable and intentionally use exclusive creation.
- **Noisy/invalid trial:** retain the run and its `validity.json`/noise fields. A legitimate loss or missed incident is an outcome, not a reason to retry; only the runner's declared infrastructure-retry rules apply.
- **Budget/model fields unresolved:** complete measured calibration and create a resolved execution config. Do not substitute guessed thresholds or cost values.
- **Insufficient disk/tmpfs:** check the host's available disk and staging caps before collection; the runner uses a per-trial output bound and checks overhead for transport framing.
- **Reproducing the report:** `latex_report/main.tex` is compiled with IEEEtran; its generated figure sources and bibliography are in `latex_report/`.

The numerical pilot values describe this recorded Linux host and exact configuration only. No fixed 1% result is presented as an adaptive-policy result.
