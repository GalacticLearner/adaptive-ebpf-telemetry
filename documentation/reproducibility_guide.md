# Reproducibility Guide

## A. Project overview

This project implements adaptive Linux kernel telemetry using eBPF. A low-cost scheduler sentinel tracks activity in target tasks while a user-space C/libbpf agent controls detailed syscall sampling. The intended operating principle is to retain inexpensive telemetry during healthy periods and increase detail when a calibrated signal indicates an anomaly, subject to a declared 5% application-throughput-loss budget.

The implementation provides three detail modes (LOW, MEDIUM, HIGH), two adaptive mechanisms (GATE and SWITCH), fixed-policy comparisons, CPU and tmpfs-I/O workloads, controlled futex incidents, event/loss accounting, and a Python experiment and analysis harness. The actual recorded evidence in this repository is a passing privileged Linux smoke plus calibration and a four-block paired fixed 1% pilot. The pilot is not an adaptive-versus-fixed evaluation; its limits and noise flags are preserved below.

## B. Repository structure

| Path | Purpose |
|---|---|
| `src/bpf/` | CO-RE scheduler sentinel and raw syscall detail programs |
| `src/agent/` | libbpf loading, event loop, mode/link changes, bounded sink |
| `src/common/` | policy, cost accounting, timestamps, wire format |
| `src/workloads/` | deterministic CPU/I/O workloads and known-count helper |
| `runner/` | CLI, host readiness, calibration, trials, immutable attempt records |
| `analysis/` | validation, metrics, statistics, figures and timelines |
| `configs/` | protocol, pilot, calibration, confirmatory, robustness configurations |
| `schemas/` | closed JSON schemas for run/config records |
| `data/calibration/`, `data/pilot/` | raw sealed calibration and pilot attempts |
| `results/` | derived validation, effects and summaries |
| `state/` | host/toolchain inventory and privileged smoke evidence |
| `tests/`, `tools/` | automated checks and host/configuration utilities |
| `latex_report/` | IEEEtran source, bibliography, figure generator and report |

Original project structure and evidence are retained in place; no large data or virtual environment is duplicated.

## C. Hardware and environment used

The saved host inventory (`state/host.json`) was captured on 2026-11-14 and identifies:

- Ubuntu 26.04 LTS, x86-64, kernel `7.0.0-31-generic`.
- 20 logical CPUs; host inventory reports about 14.5 GiB RAM.
- Current machine CPU inventory: 12th Gen Intel Core i7-12700H.
- Readable BTF, cgroup v2, scheduler switch and raw syscall tracepoints.
- Privileged smoke completed successfully on the recorded host.

Tool versions recorded for this environment:

| Tool | Recorded version |
|---|---|
| Python | 3.14.4 |
| Clang BPF compiler | 18.1.8 |
| GCC/`cc` | 15.2.0 |
| GNU Make | 4.4.1 |
| bpftool | 7.7.0 (reports its runtime libbpf as 1.7) |
| pkg-config | 2.5.1 |
| Agent build libbpf | pinned source build 1.5.1 |

Exact resolved Ubuntu package and Python dependency versions are preserved in `state/bootstrap/`, `requirements.lock`, and `requirements-analysis.lock`. Re-run `runner doctor` when reproducing on another host; do not assume the same kernel features or CPU placement.

## D. Software requirements

Use an authorized x86-64 Linux system with:

- BTF available at `/sys/kernel/btf/vmlinux`.
- `sched_switch`, raw `sys_enter`/`sys_exit`, BPF ring buffer, and cgroup v2.
- Permission to load tracing programs (the experiment uses root).
- Python 3.11+, GNU Make, GCC, Clang 18 with the BPF backend, bpftool, pkg-config, libelf headers, and zlib.

Python direct/transitive pins are included in `requirements.lock`; analysis extras including NumPy and Matplotlib are pinned in `requirements-analysis.lock`. The Linux bootstrap verifies the libbpf 1.5.1 archive checksum and builds the library locally for the agent.

## E. Installation and setup

From the project root on Ubuntu:

```bash
bash artifact/bootstrap-linux.sh
sudo .venv/bin/python -m runner doctor --output state/host.json
PKG_CONFIG_PATH="$PWD/.deps/libbpf-1.5.1/lib/pkgconfig" \
  make CLANG=clang-18 build
```

The bootstrap installs exact Ubuntu archive package candidates, creates the virtual environment, builds libbpf, obtains target BTF, generates libbpf skeletons, and compiles the application. Review `artifact/bootstrap-linux.sh` before running it because apt installs packages. It does not change kernel, boot, or security policy.

Run the bounded known-count smoke on the authorized host:

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

The existing successful smoke is preserved at `state/evidence/linux-smoke-20261114-001/`. Use a new output path for a repeat test; do not overwrite existing evidence.

## F. Configuration

Configurations are YAML and validated against schemas. Main fields:

- `host`: kernel/toolchain locks, CPU placement, cgroup root, and required BPF features.
- `workload`: CPU or I/O family, worker count, compute repeats, read sizes, working set, drift, timings, seeds, and output limits.
- `incidents`: incident kind, durations, randomized onset/jitter, spacing, timeouts, and background behavior.
- `sentinel`: scheduler hook, target roles, 5 ms bins, ring depth, read lag, and missing-data behavior.
- `detail`: raw syscall hooks, allowlist, sampling probabilities, 8 MiB ring/queue, sink, and overflow counters.
- `detector`: transform, scale floor, normal-model training period, threshold candidates, tick period, recovery, and gap behavior.
- `controller`: GATE/SWITCH mechanism, initial mode, 250 ms dwell, hysteresis, 5% budget, and optional supervisor.
- `experiment`: policy/workload/background/drift matrix, paired blocks, retries, noise thresholds, and host selection.
- `analysis`: block-paired estimand, bootstrap draws, confidence level, endpoints, and multiplicity handling.

LOW selects no detailed events, MEDIUM selects 10% of eligible syscall entries, and HIGH selects all eligible entries. FIX_Q01 is the separate 1% pilot baseline. Null detector, host, rate, or cost values are unresolved calibration inputs, not defaults; freeze rejects unresolved required fields.

## G. Execution

### Collect calibration data

Collection commands require the privileged Linux agent; use separate terminal invocations for each finished collection/analysis stage. Example rate-stage collection and derivation:

```bash
sudo .venv/bin/python -m runner calibrate --collect --stage rate \
  --config state/calibration-host-20261114.yaml \
  --output data/calibration/rate-reproduction
.venv/bin/python -m runner calibrate --stage rate \
  --input data/calibration/rate-reproduction \
  --output state/calibration/rates-reproduction.json
```

Follow `artifact/CALIBRATION.md` for rate/storage, perturbation, independent normal training/validation, action-cost, attribution, and precision stages. Each stage uses a fresh directory. Do not train on final incident outcomes.

### Run the recorded pilot configuration

The saved run uses `state/pilot-q01-4blocks-20261114.yaml`; its design is two workload families, low background, no drift, four paired blocks, and policies NONE/FIX_Q01. A fresh run can be executed as:

```bash
sudo .venv/bin/python -m runner pilot \
  --config state/pilot-q01-4blocks-20261114.yaml \
  --study primary --limit 16 \
  --output data/pilot/reproduction-q01
```

This command runs workloads and BPF collection; it is not a dry run. The existing immutable pilot is under `data/pilot/bounded-q01-4blocks-20261114-001/`. Do not reuse its directory.

### Run full campaigns

Only after all calibration fields are resolved and a freeze record is produced:

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

The configured primary matrix is 56 cells and 672 trials at 12 paired blocks; this is a planned protocol estimate. Full execution can require many hours. The runner serializes trials under a host lock and records retries as new attempts.

## H. Experimental reproduction and analysis

Saved pilot validation and analysis can be regenerated without launching workloads:

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

The recorded pilot tests only fixed 1% sampling against NONE. The code/configuration also supports SENT, fixed LOW/MEDIUM/HIGH, ADAPT_GATE, and ADAPT_SWITCH; no such adaptive comparison is reported from this pilot. To select a policy, set the policy in the experiment configuration rather than editing runtime code.

## I. Results and output interpretation

Important files:

- `data/pilot/bounded-q01-4blocks-20261114-001/campaign.json`: trial schedule and policy pairing.
- Each attempt directory: `manifest.json`, `resolved_config.json`, `intended_schedule.json`, `truth.jsonl`, `counters.json`, `resources.csv`, `validity.json`, noise record, raw trace archive, and `seal.json`.
- `results/pilot/bounded-q01-4blocks-20261114-001/results.json`: paired estimates, intervals, and hypothesis decisions.
- `effects.csv`: compact result table.
- `run_metrics.json`: attempt-level outcomes, detection metrics, counters, and mode activity.
- `validation.json`: validation errors/warnings.
- `state/evidence/linux-smoke-20261114-001/checks.json`: known-count smoke checks.
- `latex_report/figures/`: report architecture and measured pilot graph.

Actual four-block pilot observations for FIX_Q01 vs NONE:

| Workload | Estimated throughput loss | 95% block-bootstrap interval | Capture | 95% interval | On-time alert recall |
|---|---:|---:|---:|---:|---:|
| CPU | 1.85% | −0.63% to 5.60% | 1.17% | 1.02% to 1.35% | 0% |
| I/O | 11.21% | 10.85% to 11.46% | 1.00% | 0.88% to 1.16% | 0% |

There are four paired blocks for each workload. All 16 attempt records were valid and carried the external-CPU noise warning. The runner's formal 5% budget decision is inconclusive because the sample is below its eight-block decision threshold. Capture, alert recall, throughput loss, and transport loss are distinct metrics. Ring-buffer and sink-drop counts were zero in the smoke and recorded pilot; one in-flight event was classified abandoned in each four-run pilot workload set.

## J. Troubleshooting

- **Permission or attach failure:** run `doctor`; verify root/tracing permissions, target BTF, cgroup v2, and exact tracepoints.
- **Clang/BPF compile failure:** use Clang 18 BPF target and regenerate BTF-derived skeletons from the actual kernel. A compile-only check does not replace a real privileged load test.
- **libbpf not found or wrong version:** set `PKG_CONFIG_PATH` to `.deps/libbpf-1.5.1/lib/pkgconfig`; preserve `CLANG=clang-18`.
- **Output directory exists:** select a fresh path; attempt writers are exclusive to preserve immutable evidence.
- **Noise warning:** retain it and report it. Do not silently drop valid noisy runs or retry a scientifically unfavorable result.
- **Unresolved calibration:** collect the corresponding calibration population and create a separate resolved execution config; do not guess thresholds, throughput costs, or event-rate limits.
- **Storage or staging limit:** check available disk and configured RAM/tmpfs bounds; output accounting includes 72-byte transport strides and framing.

## K. Reproducibility notes

The experiment uses root, target-kernel BTF and tracepoints, and cgroup v2. CPU frequency, host contention, background tasks, kernel version, CPU placement, and thermal state can affect outcomes. The run harness records host/noise state and preserves failed attempts. It does not change scheduler policy, governor, turbo, or security settings. A new host requires new host discovery, smoke, and calibration; do not combine runs across hosts as one paired population.

To compile the IEEE report from its source:

```bash
cd latex_report
python3 generate_figures.py
pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

The LaTeX source, bibliography, and generated figures are all part of this repository. No ZIP archive is created by the project.
