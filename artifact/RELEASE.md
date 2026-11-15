# Submission handoff

The project is organized for the course submission without creating a ZIP archive. The working source and original experiment directories remain in place. The root `README.md`, `latex_report/`, and `documentation/` provide the project overview, IEEE report, and reproduction instructions.

The recorded Linux evidence is preserved in `state/evidence/linux-smoke-20261114-001/`, `data/calibration/`, and `data/pilot/`; derived pilot summaries are in `results/pilot/bounded-q01-4blocks-20261114-001/`. Immutable attempts include their manifests, validation/noise records, counters, seals, and raw trace data. Do not edit or replace those experiment outputs.

The current four-block pilot is a fixed NONE/FIX_Q01 comparison and carries external-CPU noise warnings on all attempts. The submission report treats it as exploratory and does not claim adaptive-policy advantage or formal budget compliance.

Python pins, Linux package/tool inventory, BPF archive checksum, and report/reproduction sources are retained in the repository. No final submission ZIP or unrelated release bundle is generated here.
