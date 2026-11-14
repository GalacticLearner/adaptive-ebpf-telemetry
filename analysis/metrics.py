from __future__ import annotations

import bisect
import csv
import json
from pathlib import Path
import statistics

from .wire import records
from .stats import poisson_rate_interval
from runner.util import read_json


def jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{number}: invalid JSON") from exc


def csv_rows(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def match_alerts(incidents, alerts, *, after_ns=1_000_000_000):
    valid = sorted((i for i in incidents if i["valid"]), key=lambda x: x["start_ns"])
    used = set()
    matches = {}
    false = []
    for alert in sorted(alerts, key=lambda a: a["start_ns"]):
        found = next((i for i in valid if i["episode_id"] not in used and i["start_ns"] <= alert["start_ns"] <= i["end_ns"] + after_ns), None)
        if found is None:
            false.append(alert)
        else:
            eid = found["episode_id"]
            used.add(eid)
            matches[eid] = {"alert": alert, "on_time": alert["start_ns"] <= found["end_ns"],
                            "onset_to_alert_ns": alert["start_ns"] - found["start_ns"]}
    already = [i["episode_id"] for i in valid if i["episode_id"] not in matches and any(a["start_ns"] < i["start_ns"] < a["end_ns"] for a in alerts)]
    return {"matches": matches, "false_alerts": false, "already_alerting": already,
            "recall": len(matches) / len(valid) if valid else None,
            "on_time_recall": sum(m["on_time"] for m in matches.values()) / len(valid) if valid else None,
            "precision": len(matches) / len(alerts) if alerts else None}


def alerts_from_ticks(ticks, start, end):
    alerts, active = [], None
    for t in ticks:
        ns, state = int(t["monotonic_ns"]), bool(int(t["alert"]))
        if ns >= end:
            break
        if state and active is None:
            active = {"start_ns": ns, "end_ns": end}
        elif not state and active is not None:
            active["end_ns"] = ns
            if active["start_ns"] >= start:
                alerts.append(active)
            active = None
    if active and active["start_ns"] >= start:
        alerts.append(active)
    return alerts


def throughput(app, start, end):
    """Cumulative-counter interpolation; return sampling resolution with each rate."""
    total = 0.0
    max_gap = 0
    for worker in sorted({r["worker"] for r in app}):
        rows = sorted((r for r in app if r["worker"] == worker), key=lambda x: int(x["monotonic_ns"]))
        times = [int(r["monotonic_ns"]) for r in rows]
        def count_at(ns):
            nonlocal max_gap
            right = bisect.bisect_left(times, ns)
            if right < len(times) and times[right] == ns:
                return float(rows[right]["successful"])
            if right == 0 or right == len(times):
                raise ValueError("application samples do not bracket measured phase")
            a, b = rows[right - 1], rows[right]
            dt = int(b["monotonic_ns"]) - int(a["monotonic_ns"])
            max_gap = max(max_gap, dt)
            return int(a["successful"]) + (int(b["successful"]) - int(a["successful"])) * (ns - int(a["monotonic_ns"])) / dt
        total += count_at(end) - count_at(start)
    return {"units_per_s": total / ((end - start) / 1e9), "completed_interpolated": total,
            "boundary_resolution_ns": max_gap, "method": "linear interpolation of 100ms cumulative samples"}


def matches_source_futex(event, incident):
    if incident["kind"] != "futex" or not incident["valid"] or event.syscall_id != 202:
        return False
    return any(helper["tid"] == event.tid and helper["first_ns"] <= event.entry_ns <= helper["last_ns"]
               for helper in incident["helpers"])


def measure_attempt(path):
    path = Path(path)
    manifest = read_json(path / "manifest.json")
    cfg = read_json(path / "resolved_config.json")
    truth = list(jsonl(path / "truth.jsonl"))
    epoch, = [t for t in truth if t["type"] == "epoch"]
    start, end = epoch["start_ns"], epoch["end_ns"]
    incidents = [t for t in truth if t["type"] == "episode"]
    ticks = csv_rows(path / "ticks.csv") if (path / "ticks.csv").exists() else []
    alerts = alerts_from_ticks(ticks, start, end)
    detection = match_alerts(incidents, alerts, after_ns=int(cfg["analysis"]["match_after_s"] * 1e9))
    if manifest["policy"] == "NONE":
        detection = {"recall": None, "on_time_recall": None, "precision": None, "matches": {}, "false_alerts": [], "already_alerting": []}
    transitions = list(jsonl(path / "transitions.jsonl")) if (path / "transitions.jsonl").exists() else []
    lows = [t for t in transitions if t["action"] == "gate_low_cutoff"]
    captured = {i["episode_id"]: {"pairs": 0, "common_pairs": 0, "during_pairs": 0, "censored": 0, "first_entry_ns": None, "first_exit_ns": None,
                                  "first_receipt_ns": None} for i in incidents}
    source = path / "detail.bin.gz" if (path / "detail.bin.gz").exists() else path / "detail.bin"
    if source.exists():
        for event, receipt in records(source):
            for i in incidents:
                tids = {h["tid"] for h in i["helpers"]}
                if event.tid not in tids or not i["start_ns"] <= event.entry_ns <= i["end_ns"] or not matches_source_futex(event, i):
                    continue
                m = captured[i["episode_id"]]
                m["pairs"] += 1
                m["during_pairs"] += event.exit_ns <= i["end_ns"]
                censored = any(event.entry_ns < t["desired_ns"] and event.exit_ns > t["desired_ns"] + cfg["detail"]["drain_grace_ms"] * 1_000_000 for t in lows)
                m["censored"] += censored
                m["common_pairs"] += not censored
                if m["first_entry_ns"] is None or event.entry_ns < m["first_entry_ns"]:
                    m["first_entry_ns"] = event.entry_ns
                if m["first_exit_ns"] is None or event.exit_ns < m["first_exit_ns"]:
                    m["first_exit_ns"] = event.exit_ns
                if m["first_receipt_ns"] is None or receipt < m["first_receipt_ns"]:
                    m["first_receipt_ns"] = receipt
    episode_metrics = []
    for i in incidents:
        m = captured[i["episode_id"]]
        denominator = i["eligible_calls"] if i["kind"] == "futex" and i["valid"] else 0
        if denominator and m["pairs"] > denominator:
            raise ValueError("detail capture exceeds independently counted source calls")
        matched = detection["matches"].get(i["episode_id"])
        ack_delay=None;already_detailed=False
        if matched:
            alert_ns=matched["alert"]["start_ns"]
            actions=sorted((t for t in transitions if t["action"] in ("activate","publish","gate_low_cutoff","drain_complete")),key=lambda t:t["ack_ns"])
            prior=[t for t in actions if t["ack_ns"]<=alert_ns]
            if prior and prior[-1]["mode"]>0:
                ack_delay=0;already_detailed=True
            else:
                later=next((t for t in actions if t["ack_ns"]>=alert_ns and t["mode"]>0),None)
                if later:ack_delay=later["ack_ns"]-alert_ns
        episode_metrics.append({**m, "episode_id": i["episode_id"], "nominal_ms": i["nominal_ms"],
             "actual_ms": (i["end_ns"] - i["start_ns"]) / 1e6, "phase": int(cfg["workload"]["drift"] and i["start_ns"] >= start + cfg["workload"]["drift_at_s"] * 1e9),
             "overshoot_ms":(i["end_ns"]-i["start_ns"])/1e6-i["nominal_ms"],
             "late_start_ms":(i["start_ns"]-i["intended_ns"])/1e6,
             "already_alerting":i["episode_id"] in detection["already_alerting"],
             "valid": i["valid"], "source_calls": denominator or None,
             "capture": m["pairs"] / denominator if denominator else None,
             "common_capture": m["common_pairs"] / denominator if denominator else None,
             "useful1": m["during_pairs"] >= 1 if denominator else None,
             "useful10": m["during_pairs"] >= 10 if denominator else None,
             "detected": bool(matched) if manifest["policy"] != "NONE" else None,
             "on_time": matched["on_time"] if matched else False if manifest["policy"] != "NONE" else None,
             "alert_delay_ns": matched["onset_to_alert_ns"] if matched else None,
             "alert_to_ready_ack_ns":ack_delay,"already_detailed":already_detailed,
             "first_pair_delay_ns":m["first_exit_ns"]-i["start_ns"] if m["first_exit_ns"] is not None else None,
             "receipt_delay_ns": m["first_receipt_ns"] - i["start_ns"] if m["first_receipt_ns"] is not None else None,
             "missed_or_censored": matched is None})
    app = csv_rows(path / "app.csv")
    boundaries = [start, end]
    if cfg["workload"]["drift"]:
        boundaries.insert(1, start + int(cfg["workload"]["drift_at_s"] * 1e9))
    phases = []
    for phase, (lo, hi) in enumerate(zip(boundaries, boundaries[1:])):
        phases.append({"phase": phase, **throughput(app, lo, hi)})
    in_epoch = [t for t in ticks if start <= int(t["monotonic_ns"]) < end]
    occupancy = {str(m): sum(int(t["applied"]) == m for t in in_epoch) / len(in_epoch) if in_epoch else None for m in range(3)}
    quiet_seconds = (end - start) / 1e9 - sum((min(end, i["end_ns"] + 1_000_000_000) - i["start_ns"]) / 1e9 for i in incidents if i["valid"])
    drift_at = start + int(cfg["workload"]["drift_at_s"] * 1e9) if cfg["workload"]["drift"] else None
    drift_false = [a for a in detection["false_alerts"] if drift_at is not None and drift_at <= a["start_ns"] <= drift_at + 1_000_000_000]
    quiet_false = len(detection["false_alerts"]) - len(drift_false)
    return {"trial": manifest["trial"], "policy": manifest["policy"], "population": manifest["population"],
            "noise_flags":read_json(path/"validity.json")["noise_flags"],
            "synthetic": manifest["synthetic"], "phases": phases, "episodes": episode_metrics,
            "detection": {k: v for k, v in detection.items() if k != "matches"}, "occupancy": occupancy,
            "quiet_false_alarm": poisson_rate_interval(quiet_false, max(1e-9, quiet_seconds - (1 if drift_at is not None else 0)) / 3600),
            "benign_change_false_alerts": len(drift_false),
            "mode_changes_per_min": sum(t["action"] in ("activate", "publish", "drain_complete", "gate_low_cutoff") and start <= t["ack_ns"] < end for t in transitions) / ((end - start) / 60e9),
            "counters": read_json(path / "counters.json") if (path / "counters.json").exists() else None}
