# Adaptive eBPF Telemetry with an Explicit Overhead Budget

This Linux systems project studies an adaptive eBPF telemetry pipeline that keeps a low-cost scheduler signal active and changes detailed syscall collection according to detected workload changes. The implementation pairs two collection mechanisms—entry-time sampling with persistent tracepoint links (GATE) and detail-link attachment switching (SWITCH)—with fixed-policy baselines, explicit event-loss accounting, and a declared 5% application-throughput-loss budget.

## Research question

At a declared application-performance budget, how do in-probe sampling and changing detail-hook attachment state affect short-incident visibility and the overhead–capture trade-off?

## Implemented components

- **Kernel instrumentation:** CO-RE eBPF programs at `sched/sched_switch` and raw syscall entry/exit tracepoints. The sentinel aggregates target scheduling activity in rotating per-CPU bins; detail probes sample allowlisted syscalls.
- **Collection modes:** LOW (no detailed selections), MEDIUM (10% sampling), and HIGH (all eligible entries), plus a fixed 1% sampling policy used in the recorded pilot.
- **Controller and agent:** C/libbpf collector, event sink, mode-transition logic, anomaly score, dwell/hysteresis, and optional resource supervisor.
- **Workloads:** checksum-producing CPU work, prefaulted tmpfs reads, controlled futex incidents, background contention, and configurable workload drift.
- **Experiment harness:** Python trial orchestration, immutable attempt records, host checks, exact policy pairing, validation, statistics, and output packaging.
- **Evaluation:** paired application throughput, incident capture and alert recall, mode occupancy/transitions, event counters, and separate loss categories.

The adaptive policies and full confirmatory matrix are defined in the code and configurations. The recorded Linux pilot is narrower: it compares `NONE` with fixed 1% sampling for CPU and I/O workloads, four paired blocks per workload. The report therefore describes the pilot as pilot evidence and does not present it as a completed adaptive-versus-fixed evaluation.

## Recorded Linux evidence

The recorded host is Ubuntu 26.04 LTS x86-64, kernel `7.0.0-31-generic`, with 20 logical CPUs and about 14.5 GiB RAM. The privileged eBPF smoke passed on 2026-11-14: at full sampling, 2,000 eligible syscall entries produced 2,000 completed, emitted, consumed, and written records with no ring-buffer or sink drops. The low and sentinel-only checks also passed.

In the four-block 1% pilot, estimated throughput loss was **1.85%** for CPU (95% block-bootstrap interval −0.63% to 5.60%) and **11.21%** for I/O (10.85% to 11.46%). Common-cutoff incident capture was 1.17% and 1.00%, respectively; on-time alert recall was 0% in both. The predeclared 5% budget result remains inconclusive under the runner's underpowered-sample rule. All pilot attempts were valid but carried the external-CPU noise warning. These results are not evidence of an adaptive-policy benefit.

The exact run records and analysis are preserved under [`data/`](data), [`results/`](results), and [`state/evidence/`](state/evidence/). See the [claim/evidence boundary](research/claims.md) before interpreting them.

## Repository map

```text
analysis/       validation, metrics, statistics, plots, and timelines
artifact/       Linux bootstrap, reproduction/calibration instructions, release notes
configs/        pilot, calibration, confirmatory, robustness, protocol, and schema registry
context/        assignment and preserved project context
data/           immutable calibration and pilot attempts; synthetic data is separate
documentation/  submission reproducibility guide (Markdown and PDF)
latex_report/   IEEEtran report source, bibliography, figures, and compiled PDF
paper/          evidence ledgers and current manuscript material
research/       literature/evidence-access records and claim boundary
runner/         CLI, host checks, trial orchestration, validation, analysis, packaging
schemas/        strict JSON schemas for configurations and run artifacts
src/            C user-space agent/workloads and eBPF programs
state/          host/toolchain locks and smoke/test evidence
tests/          C and Python policy, cost, and analysis tests
tools/           host/configuration/schema utilities
```

The repository already has a coherent structure, so its original source and experiment directories are retained rather than copied into a second `code/` tree.

## Requirements

- x86-64 Linux with readable kernel BTF, `sched_switch`, raw syscall tracepoints, ring-buffer support, cgroup v2, and permission to load the required BPF programs (the recorded experiment used root).
- Python 3.11 or later; the recorded host used Python 3.14.4.
- GCC/`cc`, Clang 18 with the BPF backend, `bpftool`, `pkg-config`, libelf development headers, zlib, and GNU Make. The bootstrap script builds pinned libbpf 1.5.1 for the agent.
- Exact Python dependency pins are in [`requirements.lock`](requirements.lock) and [`requirements-analysis.lock`](requirements-analysis.lock).

## Setup and build

On an authorized Ubuntu x86-64 Linux host:

```bash
bash artifact/bootstrap-linux.sh
sudo .venv/bin/python -m runner doctor --output state/host.json
PKG_CONFIG_PATH="$PWD/.deps/libbpf-1.5.1/lib/pkgconfig" \
  make CLANG=clang-18 build
```

The bootstrap script installs the required Ubuntu packages, verifies the libbpf source archive hash, creates `.venv/`, generates target-kernel BTF/skeletons, and compiles the project. Review the script before running it; it makes package-manager changes but does not change kernel, boot, or security policy.

## Run and analyze

The smoke check is privileged and runs a bounded known-count test:

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

For an experiment, use a fresh output directory so existing immutable attempts are preserved. For example, the four-block `NONE`/`FIX_Q01` pilot configuration is `state/pilot-q01-4blocks-20261114.yaml`:

```bash
sudo .venv/bin/python -m runner pilot \
  --config state/pilot-q01-4blocks-20261114.yaml \
  --study primary --limit 16 \
  --output data/pilot/reproduction-q01
```

Validate, analyze, and render plots from that run:

```bash
.venv/bin/python -m runner validate \
  --input data/pilot/reproduction-q01 \
  --output state/validation-reproduction-q01.json
.venv/bin/python -m runner analyze \
  --input data/pilot/reproduction-q01 \
  --output results/reproduction-q01 --figures
.venv/bin/python -m runner report \
  --input results/reproduction-q01 \
  --output paper/reproduction-q01
```

Do not run the full confirmatory/supplementary campaign without first resolving calibration values and reviewing the protocol. Matrix estimates and detailed steps are in [`artifact/REPRODUCE.md`](artifact/REPRODUCE.md).

## Submission files

- IEEE conference report: [`latex_report/main.tex`](latex_report/main.tex) and [`latex_report/report.pdf`](latex_report/report.pdf)
- Reproducibility instructions: [`documentation/reproducibility_guide.md`](documentation/reproducibility_guide.md) and its PDF
- Experiment-specific caveats and claim boundaries: [`research/claims.md`](research/claims.md)
- Assignment-to-implementation traceability: [`requirements_traceability.md`](requirements_traceability.md)

The report uses measured Linux smoke and pilot evidence, distinguishes it from planned/derived analysis, and avoids an unsupported claim that the adaptive policies outperform fixed policies.
