from __future__ import annotations

from pathlib import Path
import csv
import json

from analysis.pipeline import find_attempts
from analysis.validate import validate_attempt
from analysis.metrics import csv_rows, jsonl
from analysis.metrics import measure_attempt
import math
import statistics
from .calibration import derive_precision, train_cost_table, train_detector
from .util import digest, read_json, write_json


def _read_effects(path, population):
    document=read_json(path)
    if document.get("population")!=population or document.get("synthetic") is not False:
        raise ValueError(f"requires real {population} input provenance")
    for name, checksum in document["attempt_seals"].items():
        p=Path(name)
        if digest(p)!=checksum or not validate_attempt(p.parent)["valid"]:
            raise ValueError(f"unvalidated calibration input:{name}")
    if not document["attempt_seals"]:raise ValueError("source attempt seals are mandatory")
    return document["rows"]


def _normal(path):
    result=[];hashes={}
    for attempt in find_attempts(path):
        checked=validate_attempt(attempt)
        if not checked["valid"]:raise ValueError(f"invalid normal calibration attempt:{attempt}")
        m=read_json(attempt/"manifest.json");c=read_json(attempt/"resolved_config.json")
        if m["synthetic"] or m["population"]!="calibration" or c["incidents"]["kind"]!="none" or c["workload"]["drift"]:
            raise ValueError("normal detector training requires real calibration without incidents/drift")
        epoch=next(t for t in jsonl(attempt/"truth.jsonl") if t["type"]=="epoch")
        deployment=f"{c['workload']['family']}/{c['incidents']['background']}/max-bin"
        selected=[]
        for row in csv_rows(attempt/"bins.csv"):
            ns=int(row["absolute_bin"])*5_000_000
            if epoch["start_ns"]<=ns and ns+5_000_000<=epoch["end_ns"]:
                value={**row,"deployment":deployment,"block_id":m["trial"]["block_id"]}
                result.append(value);selected.append(value)
        groups={}
        for row in selected:groups.setdefault(int(row["absolute_bin"])//20,[]).append(row)
        for index,chunk in groups.items():
            if len(chunk)==20 and all(int(r["valid"]) for r in chunk):
                result.append({"deployment":deployment.rsplit("/",1)[0]+"/total","block_id":m["trial"]["block_id"],
                               "absolute_bin":index,"count":sum(int(r["count"]) for r in chunk),"valid":1})
        hashes[str(attempt/"seal.json")]=digest(attempt/"seal.json")
    if not result:raise ValueError("no normal calibration bins")
    return result,hashes


def _effects(path,population):
    if Path(path).is_file():return _read_effects(path,population)
    attempts=find_attempts(path);blocks={};result=[]
    for attempt in attempts:
        if not validate_attempt(attempt)["valid"]:raise ValueError(f"invalid effect input:{attempt}")
        m=read_json(attempt/"manifest.json")
        if m["synthetic"] or m["population"]!=population:raise ValueError("model populations must be real and separate")
        blocks.setdefault(m["trial"]["block_id"],{})[m["policy"]]=(attempt,measure_attempt(attempt))
    for bid,policies in blocks.items():
        if "NONE" not in policies:continue
        reference=policies["NONE"][1]
        for policy,(attempt,record) in policies.items():
            if policy=="NONE":continue
            ticks=csv_rows(attempt/"ticks.csv")
            config=read_json(attempt/"resolved_config.json")
            epoch=next(t for t in jsonl(attempt/"truth.jsonl") if t["type"]=="epoch")
            for phase in record["phases"]:
                control=next(p for p in reference["phases"] if p["phase"]==phase["phase"])
                row={"population":population,"synthetic":False,"block_id":bid,
                     "log_ratio":math.log(phase["units_per_s"]/control["units_per_s"])}
                if population=="pilot":
                    if policy not in ("ADAPT_GATE","ADAPT_SWITCH"):continue
                    gate=policies.get("ADAPT_GATE");switch=policies.get("ADAPT_SWITCH")
                    if not gate or not switch:continue
                    def capture(r):return [e["common_capture"] for e in r[1]["episodes"] if e["valid"] and e["phase"]==phase["phase"] and e["common_capture"] is not None]
                    g,s=capture(gate),capture(switch)
                    if not g or not s:continue
                    row["capture_difference"]=statistics.mean(g)-statistics.mean(s);result.append(row)
                else:
                    mode={"SENT":0,"FIX_LOW_GATE":0,"FIX_MED":1,"FIX_HIGH":2}.get(policy)
                    if mode is None:continue
                    boundary=epoch["start_ns"]+int(config["workload"]["drift_at_s"]*1e9)
                    lo=epoch["start_ns"] if phase["phase"]==0 else boundary
                    hi=boundary if config["workload"]["drift"] and phase["phase"]==0 else epoch["end_ns"]
                    phase_ticks=[t for t in ticks if lo<=int(t["monotonic_ns"])<hi]
                    rates=[float(t["rate"]) for t in phase_ticks if t.get("rate") and math.isfinite(float(t["rate"]))]
                    utils=[float(t["utilization"]) for t in phase_ticks if t.get("utilization") and math.isfinite(float(t["utilization"]))]
                    if not rates or not utils:continue
                    mechanisms=("SWITCH",) if policy=="SENT" else ("GATE",) if policy=="FIX_LOW_GATE" else ("GATE","SWITCH")
                    for mechanism in mechanisms:result.append({**row,"mechanism":mechanism,"mode":mode,
                        "sentinel_rate":statistics.mean(rates),"utilization":statistics.mean(utils)})
    return result


def calibrate(args,c):
    if args.collect:
        from .collect import collect
        return collect(args,c)
    if not args.input:
        raise ValueError("--input real calibration attempts/effects required; use artifact/CALIBRATION.md collection commands")
    target=args.output
    if args.stage=="normal":
        if not args.validation:raise ValueError("separate --validation normal attempts required")
        training,hashes=_normal(args.input);validation,vhashes=_normal(args.validation)
        result=train_detector(training,validation,c);result["source_seals"]={**hashes,**vhashes}
        target=target or Path("state/calibration/detector.json")
    elif args.stage=="cost":
        result=train_cost_table(_effects(args.input,"calibration"),draws=c["analysis"]["bootstrap_draws"],seed=c["analysis"]["bootstrap_seed"])
        target=target or Path("state/calibration/cost.json")
    elif args.stage=="precision":
        result=derive_precision(_effects(args.input,"pilot"));target=target or Path("state/calibration/precision.json")
    elif args.stage=="perturbation":
        groups={}
        for path in find_attempts(args.input):
            if not validate_attempt(path)["valid"]:raise ValueError(f"invalid perturbation attempt:{path}")
            m=read_json(path/"manifest.json")
            if m["synthetic"] or m["population"]!="calibration":raise ValueError("perturbation requires real calibration attempts")
            scenario=m["trial"]["scenario"]
            key=(scenario["workload"],scenario["background"],m["trial"]["block_id"])
            groups.setdefault(key,{})[scenario["variant"]]=measure_attempt(path)
        from analysis.stats import paired_throughput
        comparisons=[]
        deployments=sorted({(f,b) for f,b,bid in groups})
        for family,background in deployments:
            for variant in ("no_resources","no_truth","histogram"):
                pairs=[(variants[variant]["phases"][0]["units_per_s"],variants["standard"]["phases"][0]["units_per_s"]) for (f,b,bid),variants in groups.items() if f==family and b==background and variant in variants and "standard" in variants]
                if pairs:comparisons.append({"family":family,"background":background,"variant":variant,"effect":paired_throughput([a for a,b in pairs],[b for a,b in pairs])})
        result={"schema_version":1,"comparisons":comparisons,"independent_unit":"paired block","limitation":"transport/kernel and application perturbation are separate costs"}
        target=target or Path("state/calibration/perturbation.json")
    else:
        attempts=find_attempts(args.input);rates=[]
        for path in attempts:
            if not validate_attempt(path)["valid"]:raise ValueError(f"invalid rate calibration:{path}")
            m=read_json(path/"manifest.json")
            if m["synthetic"] or m["population"]!="calibration":raise ValueError("rate calibration cannot use synthetic/final data")
            counters=read_json(path/"counters.json")
            config=read_json(path/"resolved_config.json")
            duration=config["workload"]["warmup_s"]+config["workload"]["measure_s"]+config["workload"]["drain_s"]
            rates.append({"attempt":str(path),"eligible_per_s":counters["eligible"]/duration,
                          "sink_bytes_per_s":counters["sink_bytes"]/(config["workload"]["warmup_s"]+config["workload"]["measure_s"]),
                          "seal_sha256":digest(path/"seal.json")})
        if not rates:raise ValueError("no rate calibration attempts")
        result={"schema_version":1,"rates":rates,"max_observed_average_eligible_rate":max(r["eligible_per_s"] for r in rates),
                "peak_rate_resolved":False,"limitation":"whole-run averages do not bound short helper bursts; inspect bounded burst/sustained sink tests before freeze"}
        target=target or Path("state/calibration/rates.json")
    write_json(target,result,exclusive=True)
    return {"output":str(target),"sha256":digest(target)}
