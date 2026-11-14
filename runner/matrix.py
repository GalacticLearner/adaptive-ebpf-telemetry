"""Complete cell registry with explicit matched control blocks and stable seeds."""
from __future__ import annotations

import itertools
import math
import random

from .util import canonical_hash, seed_for

CORE = ("NONE", "SENT", "FIX_LOW_GATE", "FIX_MED", "FIX_HIGH", "ADAPT_GATE", "ADAPT_SWITCH")
ADAPT = ("ADAPT_GATE", "ADAPT_SWITCH")


def schedule(config, seed, kind=None):
    inc = config["incidents"]
    kind = kind or inc["kind"]
    if kind == "none" or inc["slots"] == 0:
        return []
    rng = random.Random(seed)
    if inc["slots"]==1:
        onset=inc["first_anchor_s"]+rng.uniform(-inc["jitter_s"],inc["jitter_s"])
        return [{"episode_id":0,"kind":kind,"nominal_ms":inc["durations_ms"][0],"offset_ns":round(onset*1e9),"phase":0}]
    durations = inc["durations_ms"] if kind == "futex" else [25, 100, 500, 1000, 25, 100, 500]
    rows = []
    for half in range(2):
        values = durations.copy()
        rng.shuffle(values)
        for index, duration in enumerate(values):
            slot = 7 * half + index
            onset = inc["first_anchor_s"] + inc["spacing_s"] * slot + rng.uniform(-inc["jitter_s"], inc["jitter_s"])
            rows.append({"episode_id": slot, "kind": kind, "nominal_ms": duration,
                         "offset_ns": round(onset * 1e9), "phase": half if config["workload"]["drift"] else 0})
    for prev, current in zip(rows, rows[1:]):
        if prev["offset_ns"] + prev["nominal_ms"] * 1_000_000 >= current["offset_ns"]:
            raise ValueError("overlapping intended incident schedule")
    return rows


def studies(c, selection="all"):
    definitions = []
    def add(name, policies, backgrounds=("high",), drifts=(True,), repetitions=8, **options):
        for workload, background, drift in itertools.product(c["experiment"]["workloads"], backgrounds, drifts):
            definitions.append(dict(study=name, policies=policies, workload=workload, background=background,
                                    drift=drift, repetitions=repetitions, **options))
    if selection in ("all", "primary"):
        add("primary", tuple(c["experiment"]["policies"]), backgrounds=tuple(c["experiment"]["backgrounds"]),
            drifts=tuple(c["experiment"]["drifts"]), repetitions=c["experiment"]["blocks"])
    if selection in ("all", "supplementary"):
        add("frontier", ("NONE", "FIX_Q01", "FIX_Q50", "FIX_MED", "FIX_HIGH"), drifts=(False, True))
        add("supervisor", ("NONE", *ADAPT, "TRIGGER_GATE", "TRIGGER_SWITCH"))
        for name, option in (("no_hysteresis", {"hysteresis": False}), ("no_dwell", {"dwell_ms": 0}),
                             ("signal_total", {"signal": "total"})):
            add(name, ("NONE", *ADAPT), **option)
        for budget in (0.02, 0.10):
            add(f"budget_{budget}", ("NONE", *ADAPT), budget=budget)
        for period in (25, 500):
            add(f"period_{period}", ("NONE", *ADAPT), period_ms=period)
        for ring in (262144, 33554432):
            definitions.append(dict(study=f"buffer_{ring}", policies=("NONE", "FIX_HIGH", *ADAPT),
                                    workload="io", background="high", drift=True, repetitions=8, ring_bytes=ring))
        add("quiet", ("SENT", *ADAPT), backgrounds=("low", "high"), drifts=(False,),
            repetitions=c["experiment"]["quiet_repetitions"], kind="none", measure_s=c["experiment"]["quiet_measure_s"])
        components = ("NONE", "LOADED", "SENT", "EMPTY", "FILTER", "PAIR", "FIX_MED", "FIX_HIGH", "SHADOW", "ADAPT_GATE")
        for stats in (False, True):
            add(f"attribution_stats_{stats}", components, stats=stats)
    if selection in ("all", "robustness"):
        add("unseen_cpu", CORE, kind="cpu")
        add("isolated", CORE, placement="isolated")
        if c["experiment"]["include_second_host"]:
            add("second_host", CORE, host="secondary")
            add("second_host_short", CORE, host="secondary", short=True)
            add("second_host_quiet", ("SENT", *ADAPT), host="secondary", kind="none", drifts=(False,),
                measure_s=c["experiment"]["quiet_measure_s"])
    return definitions


def generate(c, selection="all"):
    rows = []
    for scenario in studies(c, selection):
        policies = scenario.pop("policies")
        n = scenario.pop("repetitions")
        sid = canonical_hash(scenario)[:12]
        rng = random.Random(seed_for(c["experiment"]["seed"], "order", sid))
        base_order = list(policies)
        rng.shuffle(base_order)
        shifts = list(range(len(policies)))
        rng.shuffle(shifts)
        for block in range(n):
            shift = shifts[block % len(shifts)]
            order = base_order[shift:] + base_order[:shift]
            if block // len(shifts) % 2:
                order.reverse()
            bid = f"{scenario['study']}-{sid}-b{block:03}"
            seeds = {name: seed_for(c["experiment"]["seed"], name, bid) for name in ("workload", "episode")}
            for position, policy in enumerate(order):
                rows.append({"cell_id": f"{sid}-{policy}", "block_id": bid,
                             "trial_id": f"{bid}-{policy}", "position": position, "policy": policy,
                             "scenario": scenario.copy(), "seeds": seeds.copy(),
                             "baseline_trial": f"{bid}-NONE" if "NONE" in policies else None,
                             "status": "planned"})
    return rows


def select_within_budget(c, rows, max_hours):
    if not math.isfinite(max_hours) or max_hours <= 0:
        raise ValueError("--max-hours must be a positive finite number")
    scenarios = {}
    for row in rows:
        scenario = canonical_hash(row["scenario"])
        blocks = scenarios.setdefault(scenario, {})
        blocks.setdefault(row["block_id"], []).append(row)

    budget_seconds = max_hours * 3600
    selected = []
    used_seconds = 0
    block_groups = list(scenarios.values())
    rounds = max((len(blocks) for blocks in block_groups), default=0)
    for block_index in range(rounds):
        for blocks in block_groups:
            block_ids = list(blocks)
            if block_index >= len(block_ids):
                continue
            block = blocks[block_ids[block_index]]
            duration = sum(trial_seconds(c, row) for row in block)
            if used_seconds + duration <= budget_seconds:
                selected.extend(block)
                used_seconds += duration
    if not selected:
        raise ValueError("--max-hours is too small for one complete matched block")
    return selected


def trial_seconds(c, row):
    duration = row["scenario"].get("measure_s", c["workload"]["measure_s"])
    return c["workload"]["warmup_s"] + duration + c["workload"]["drain_s"] + c["workload"]["cooldown_s"]


def estimate(c, rows):
    peak = c["detail"]["calibrated_peak_rate"]
    rate = peak if peak is not None else c["detail"]["eligible_rate_bound"]
    raw = seconds = 0
    for row in rows:
        duration = row["scenario"].get("measure_s", c["workload"]["measure_s"])
        seconds += trial_seconds(c, row)
        # Conservative q=1 for ALL policies, including quiet/attribution, plus warmup and drain.
        raw += (duration + c["workload"]["warmup_s"] + c["workload"]["drain_s"]) * rate * 88 + 4096
    counts = {}
    for row in rows:
        name = row["scenario"]["study"]
        counts[name] = counts.get(name, 0) + 1
    return {"trials": len(rows), "cells": len({r["cell_id"] for r in rows}), "studies": counts,
            "host_hours": seconds / 3600, "raw_bytes_upper_estimate": int(raw),
            "bytes_with_headroom": int(raw * (1 + c["workload"]["disk_headroom"])),
            "rate_is_calibrated": peak is not None, "assumed_peak_events_per_s": rate,
            "retry_upper_multiplier": 1 + c["experiment"]["retries"],
            "note": "Uncalibrated estimate excludes unbounded helper bursts; freeze requires measured aggregate peak. No baseline reuse across studies."}
