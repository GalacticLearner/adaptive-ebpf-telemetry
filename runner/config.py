from __future__ import annotations

import copy
import math
from pathlib import Path

import jsonschema
import yaml

from .util import ROOT, canonical_hash, digest, read_json


class ConfigError(ValueError):
    pass


def load_config(path=None):
    path = Path(path or ROOT / "configs/protocol.yaml")
    try:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        cfg["workload"].setdefault("truth_aggregation",True)
        cfg["experiment"].setdefault("resource_sampling",True)
        cfg["host"].setdefault("role","primary")
        jsonschema.validate(cfg, read_json(ROOT / "schemas/protocol.schema.json"))
    except (OSError, yaml.YAMLError, jsonschema.ValidationError) as exc:
        raise ConfigError(str(exc)) from exc
    check_semantics(cfg)
    return cfg


def check_semantics(c):
    required = {("detail", "inflight_entries"):8192,("detail", "target_entries"):128,
                ("workload", "io_bytes"):4096,("workload", "drift_io_bytes"):16384,
                ("workload", "working_set_bytes"):67108864,("workload", "publish_ms"):100,
                ("incidents", "timeout_ms"):1,("incidents", "background_period_ms"):10,
                ("incidents", "background_duty"):0.5,("detector", "recovery_ms"):500,
                ("detector", "alert_close_ms"):500,("detail", "drain_grace_ms"):20}
    for (section, key), value in required.items():
        if c[section][key] != value:
            raise ConfigError(f"{section}.{key} differs from compiled primary semantics ({value})")
    if c["detail"]["allowlist"] != ["pread64", "futex", "sched_yield", "clock_nanosleep"]:
        raise ConfigError("fixed syscall definitions must be identical across treatments")
    if c["sentinel"]["bins"] != 2048 or c["sentinel"]["bin_ms"] != 5:
        raise ConfigError("compiled sentinel ABI requires 2048 bins of 5 ms")
    if c["sentinel"]["lag_ms"] < 2 * c["sentinel"]["bin_ms"]:
        raise ConfigError("sentinel safety lag must be at least two bins")
    if c["detail"]["record_bytes"] != 64 or c["detail"]["record_version"] != 1:
        raise ConfigError("unsupported record ABI")
    for field in ("ring_bytes", "queue_bytes"):
        n = c["detail"][field]
        if n < 4096 or n & (n - 1):
            raise ConfigError(f"{field} must be a power of two >=4096")
    if c["incidents"]["kind"] == "futex" and c["incidents"]["slots"]:
        single=c["incidents"]["slots"]==1 and c["incidents"]["durations_ms"]==[10]
        if not single and (c["incidents"]["slots"] != 14 or c["incidents"]["durations_ms"] != [10, 25, 50, 100, 250, 500, 1000]):
            raise ConfigError("primary schedule requires fourteen slots and the seven specified durations")
        last = c["incidents"]["first_anchor_s"] + (0 if single else 13) * c["incidents"]["spacing_s"] + c["incidents"]["jitter_s"] + 1
        if c["workload"]["measure_s"] <= last:
            raise ConfigError("measured epoch cannot contain the incident schedule")
    if c["workload"]["workers"] != 2:
        raise ConfigError("primary harness requires exactly two stable application workers")
    if c["workload"]["drift"] and c["workload"]["drift_at_s"] >= c["workload"]["measure_s"]:
        raise ConfigError("drift must occur inside the measured epoch")
    cpus = c["host"]["cpus"]
    if cpus is not None and (len(cpus) != 4 or len(set(cpus)) != 4):
        raise ConfigError("host.cpus must contain four distinct CPU IDs")
    if c["detail"]["abi"] != "x86_64":
        raise ConfigError("unsupported architecture: explicit syscall ABI discovery required")
    if c["protocol"]["population"]!="calibration" and (not c["workload"].get("truth_aggregation",True) or not c["experiment"].get("resource_sampling",True)):
        raise ConfigError("measurement-off variants are calibration only")
    if c["experiment"]["blocks"] > c["experiment"]["max_blocks"]:
        raise ConfigError("block count exceeds preregistered cap")
    if c["detector"]["signal"]=="total" and c["detector"]["period_ms"]!=100:
        raise ConfigError("the separately calibrated total-signal ablation requires a 100ms period")


def unresolved(c, *, for_freeze=True):
    fields = [("host", "id"), ("host", "kernel_lock"), ("host", "toolchain_lock"), ("host", "cpus"),
              ("workload", "compute_repeats"), ("detail", "calibrated_peak_rate"),
              ("detail", "sink_bytes_per_second"), ("detector", "model"), ("detector", "threshold"),
              ("controller", "model")]
    missing = [f"{a}.{b}" for a, b in fields if c[a][b] is None]
    if for_freeze and c["experiment"]["blocks"] < 12:
        missing.append("experiment.blocks >= 12")
    if for_freeze and c["incidents"]["slots"]!=14:missing.append("primary freeze requires fourteen incident slots")
    return missing


def resolve(c, **updates):
    result = copy.deepcopy(c)
    for section, values in updates.items():
        result[section].update(values)
    check_semantics(result)
    return result


def model_paths(c):
    return [Path(c[s]["model"]) for s in ("detector", "controller") if c[s]["model"]]


def config_hash(c):
    return canonical_hash(c)
