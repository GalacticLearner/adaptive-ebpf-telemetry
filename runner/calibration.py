"""Calibration artifacts are derived ONLY from valid calibration/pilot attempts."""
from __future__ import annotations

import math
from pathlib import Path
import statistics
import csv

from analysis.metrics import csv_rows
from analysis.stats import bootstrap_blocks, choose_blocks, quantile
from analysis.validate import validate_attempt
from .reference import Controller, score, train_baseline
from .util import canonical_hash, digest, read_json, utc_now, write_json


def train_detector(training, validation, config):
    """Input rows: deployment, block_id, absolute_bin, count, valid; separate files."""
    if set(r["block_id"] for r in training) & set(r["block_id"] for r in validation):
        raise ValueError("normal training and validation block IDs overlap")
    result = {"schema_version": 1, "kind": "detector", "trained_at": utc_now(), "deployments": {}}
    keys = sorted({r["deployment"] for r in training})
    for key in keys:
        train = [r for r in training if r["deployment"] == key and int(r["valid"])]
        valid = [r for r in validation if r["deployment"] == key and int(r["valid"])]
        if not train or not valid:
            raise ValueError("separate nonempty normal validation is required")
        # Contiguous 5ms bins represent actual observed exposure, not wall span across runs.
        bin_seconds = .1 if key.endswith("/total") else .005
        if len(train) * bin_seconds < config["detector"]["training_min_s"] or len(valid) * bin_seconds < config["detector"]["training_min_s"]:
            raise ValueError("at least 10 minutes observed normal training AND validation per deployment required")
        baseline = train_baseline([int(r["count"]) for r in train])
        chosen, achieved = 12, None
        for high in config["detector"]["threshold_candidates"]:
            alerts, ticks = 0, 0
            for block in sorted({r["block_id"] for r in valid}):
                rows = sorted((r for r in valid if r["block_id"] == block), key=lambda r: int(r["absolute_bin"]))
                ctl = Controller(high=high)
                width = max(1, round(config["detector"]["period_ms"] / (bin_seconds * 1000)))
                for pos in range(0, len(rows), width):
                    chunk = rows[pos:pos + width]
                    value = score([int(r["count"]) for r in chunk], baseline)
                    alerts += ctl.tick((ticks + 1) * config["detector"]["period_ms"] * 1_000_000, value)["alert_started"]
                    ticks += 1
            rate = alerts / (len(valid) * bin_seconds / 60)
            achieved = rate
            if rate <= config["detector"]["max_normal_alerts_per_minute"]:
                chosen = high
                break
        result["deployments"][key] = {**baseline, "threshold": chosen,
             "validation_alerts_per_min": achieved, "target_met": achieved <= 1,
             "training_bins": len(train), "validation_bins": len(valid)}
    return result


def train_cost_table(rows, *, draws=10000, seed=741911):
    """Independent block effects, not individual ticks, determine uncertainty."""
    if not rows:
        raise ValueError("no calibration effects")
    if any(r["population"] != "calibration" or r.get("synthetic", False) for r in rows):
        raise ValueError("cost model accepts real calibration evidence only")
    rates = [float(r["sentinel_rate"]) for r in rows]
    bands = [quantile(rates, 1 / 3), quantile(rates, 2 / 3)]
    groups = {}
    for r in rows:
        rb = sum(float(r["sentinel_rate"]) >= b for b in bands)
        ub = sum(float(r["utilization"]) >= b for b in (.5, .8))
        key = (r["mechanism"], int(r["mode"]), rb, ub)
        groups.setdefault(key, {}).setdefault(r["block_id"], []).append(float(r["log_ratio"]))
    cells = []
    for (mechanism, mode, rb, ub), blocks in groups.items():
        if len(blocks) < 8:
            continue  # Underpowered cells never become optimistic UCLs.
        stats = bootstrap_blocks([statistics.mean(v) for v in blocks.values()], draws=draws, seed=seed,
                                 transform=lambda x: 1 - math.exp(x))
        cells.append({"mechanism": mechanism, "mode": mode, "rate_band": rb, "util_band": ub,
                      "estimate": stats["estimate"], "ucl": stats["ucl_one_sided"], "blocks": len(blocks)})
    # Mode-wide fallback uses independent blocks pooled before inference (not zero).
    fallbacks = {}
    for mechanism in ("GATE", "SWITCH"):
        for mode in range(3):
            selected = [r for r in rows if r["mechanism"] == mechanism and int(r["mode"]) == mode]
            blocks = {}
            for r in selected:
                blocks.setdefault(r["block_id"], []).append(float(r["log_ratio"]))
            if len(blocks) < 8:
                raise ValueError(f"fewer than eight independent calibration blocks for {mechanism}/{mode}")
            stats = bootstrap_blocks([statistics.mean(v) for v in blocks.values()], draws=draws, seed=seed, transform=lambda x: 1-math.exp(x))
            fallbacks[f"{mechanism}/{mode}"] = {"ucl": max([stats["ucl_one_sided"], *[c["ucl"] for c in cells if c["mechanism"] == mechanism and c["mode"] == mode]]), "blocks": len(blocks)}
    return {"schema_version": 1, "kind": "cost", "trained_at": utc_now(), "rate_tertiles": bands,
            "cells": cells, "fallbacks": fallbacks, "transitions": {},
            "transition_cost_unresolved": True, "horizon_s": 1,
            "input_hash": canonical_hash(rows)}


def derive_precision(rows):
    if not rows or any(r["population"] != "pilot" or r.get("synthetic", False) for r in rows):
        raise ValueError("precision requires real pilot blocks")
    effects = {}
    for r in rows:
        effects.setdefault(r["block_id"], []).append(r)
    if len(effects) < 8:
        raise ValueError("at least eight independent pilot blocks required")
    log_effects = [statistics.mean(float(r["log_ratio"]) for r in b) for b in effects.values()]
    capture = [statistics.mean(float(r["capture_difference"]) for r in b) for b in effects.values()]
    return choose_blocks(statistics.stdev(log_effects), statistics.stdev(capture))
