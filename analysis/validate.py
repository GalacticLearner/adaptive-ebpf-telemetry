from __future__ import annotations

import csv
from pathlib import Path
import hashlib
import gzip
import jsonschema

from runner.config import load_config, check_semantics, config_hash
from runner.util import ROOT, digest, read_json
from .metrics import csv_rows, jsonl, measure_attempt
from .wire import records


def schema(value, name):
    jsonschema.validate(value, read_json(ROOT / "schemas" / f"{name}.schema.json"))


def ledger(c):
    errors = []
    if c["eligible"] != c["selected"] + c["rejected"]:
        errors.append("entry sampling balance")
    if c["selected"] != sum(c[k] for k in ("insert_failed", "replaced", "malformed", "completed", "abandoned", "pending")):
        errors.append("selected-entry balance")
    if c["component"] != 3 and c["completed"] != c["emitted"] + c["reserve_failed"]:
        errors.append("completed export balance")
    if c["emitted"] != c["consumed"] + c["undrained"]:
        errors.append("ring delivery balance")
    if c["consumed"] != c["written"] + c["sink_drop"]:
        errors.append("sink balance")
    if c["malformed"]:
        errors.append("malformed selected pairs")
    if not c["ledger_ok"]:
        errors.append("agent declared ledger failure")
    return errors


def validate_attempt(path, *, require_seal=True):
    path = Path(path)
    errors, warnings = [], []
    try:
        m, cfg = read_json(path / "manifest.json"), read_json(path / "resolved_config.json")
        schema(m, "manifest"); schema(m["trial"], "trial"); schema(cfg, "protocol")
        check_semantics(cfg)
        if config_hash(cfg) != m["config_hash"]:
            errors.append("resolved config hash mismatch")
        if m["synthetic"] != (m["population"] == "synthetic"):
            errors.append("synthetic/population mismatch")
        if m["synthetic"] and "synthetic" not in path.parts:
            errors.append("synthetic output outside data/synthetic")
        if not m["synthetic"] and "synthetic" in path.parts:
            errors.append("kernel evidence inside synthetic namespace")
        if m["stats_enabled"] and not m["trial"]["scenario"]["study"].startswith("attribution"):
            errors.append("BPF runtime stats enabled outside attribution")
        if m["population"] == "confirmatory" and (m["code"]["dirty"] or not cfg["protocol"]["preregistration_hash"]):
            errors.append("confirmatory run not frozen on a clean source commit")
        validity = read_json(path / "validity.json"); schema(validity, "validity")
        errors.extend(validity["infrastructure_errors"])
        warnings.extend(validity["noise_flags"])
        if not m["valid"] or not validity["valid"]:
            errors.append("attempt declared invalid")
        for filename in ("app.csv", "truth.jsonl", "intended_schedule.json", "commands.jsonl", "cleanup.json"):
            if not (path / filename).is_file():
                errors.append(f"missing {filename}")
        if not m["synthetic"]:
            required=["stdout.log","stderr.log"]+(["resources.csv"] if cfg["experiment"].get("resource_sampling",True) else [])
            for filename in required:
                if not (path/filename).is_file():errors.append(f"missing {filename}")
        if require_seal:
            sealed = read_json(path / "seal.json")
            actual = {str(p.relative_to(path)) for p in path.rglob("*") if p.is_file() and p.name != "seal.json"}
            if actual != set(sealed["files"]):
                errors.append("sealed attempt file inventory changed")
            for name, expected in sealed["files"].items():
                p = (path / name).resolve()
                if not p.is_relative_to(path.resolve()):
                    errors.append("unsafe path in seal")
                elif not p.exists() or digest(p) != expected:
                    errors.append(f"sealed hash mismatch: {name}")
        truth = list(jsonl(path / "truth.jsonl"))
        epochs = [t for t in truth if t.get("type") == "epoch"]
        if len(epochs) != 1 or epochs[0]["end_ns"] <= epochs[0]["start_ns"]:
            errors.append("missing/invalid measured epoch")
        episodes = [t for t in truth if t.get("type") == "episode"]
        intended = read_json(path / "intended_schedule.json")
        if len(episodes) != len(intended):
            errors.append("intended/actual episode counts differ")
        previous = 0
        for episode in episodes:
            schema(episode, "incident")
            if not episode["valid"] or episode["start_ns"] >= episode["end_ns"]:
                errors.append("incident generation failure")
            if episode["start_ns"] < previous:
                errors.append("overlapping actual incidents")
            previous = episode["end_ns"]
            if episode["eligible_calls"] != sum(h["calls"] for h in episode["helpers"]):
                errors.append("helper/source call totals disagree")
            for h in episode["helpers"]:
                if h["calls"] != h["waits"] + h["wakes"] or h["interrupted"] > h["errors"]:
                    errors.append("helper syscall ledger")
        if any(t.get("interrupted") for t in truth if t.get("type") == "termination"):
            errors.append("workload interrupted")
        cleanup = read_json(path / "cleanup.json")
        if not all(cleanup.get(k) for k in ("children_exited", "owned_cgroups_removed", "staging_removed")):
            errors.append("owned resources remain")
        if m["policy"] != "NONE":
            for filename in ("ticks.csv", "transitions.jsonl", "bins.csv", "counters.json"):
                if not (path / filename).exists():
                    errors.append(f"missing {filename}")
            c = read_json(path / "counters.json"); schema(c, "counters"); errors.extend(ledger(c))
            raw = path / "detail.bin"
            if not raw.exists():
                raw = path / "detail.bin.gz"
            n = sum(1 for _ in records(raw))
            if n != c["written"]:
                errors.append("binary record count differs from sink written count")
            if (path / "detail.archive.json").exists():
                arch = read_json(path / "detail.archive.json")
                if digest(raw) != arch["archive_sha256"]:
                    errors.append("archive hash mismatch")
                h = hashlib.sha256()
                with gzip.open(raw, "rb") as stream:
                    for chunk in iter(lambda: stream.read(1024*1024), b""):
                        h.update(chunk)
                if h.hexdigest() != arch["raw_sha256"]:
                    errors.append("restored raw checksum mismatch")
            ticks = csv_rows(path / "ticks.csv")
            times = [int(t["monotonic_ns"]) for t in ticks]
            if any(a >= b for a, b in zip(times, times[1:])):
                errors.append("tick clock order")
            if any(int(t["gap"]) for t in ticks):
                warnings.append("sentinel gaps; recovery prohibited during uncertain ticks")
            if any(int(t["gap"]) and int(t["last_bin"]) - int(t["first_bin"]) >= 2048 for t in ticks):
                errors.append("lost unbounded sentinel history")
            if c["stats_enabled"] != m["stats_enabled"]:
                errors.append("stats manifest/counter mismatch")
        app = csv_rows(path / "app.csv")
        for worker in {r["worker"] for r in app}:
            rows = [r for r in app if r["worker"] == worker]
            if any(int(b["successful"]) < int(a["successful"]) or int(b["monotonic_ns"]) <= int(a["monotonic_ns"]) for a,b in zip(rows, rows[1:])):
                errors.append("work counters or timestamps regressed")
        if not errors:
            measure_attempt(path)
    except (OSError, ValueError, KeyError, TypeError, jsonschema.ValidationError) as exc:
        errors.append(str(exc))
    return {"path": str(path), "valid": not errors, "errors": errors, "warnings": warnings}
