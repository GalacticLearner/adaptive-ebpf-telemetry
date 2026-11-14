from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from .config import ConfigError, load_config
from .util import ROOT, command, read_json, write_json


def parser():
    p=argparse.ArgumentParser(description="Adaptive eBPF Telemetry research artifact. No default campaign.")
    subs=p.add_subparsers(dest="command",required=True)
    for name in ("doctor","build","test","calibrate","pilot","freeze","estimate-matrix","run","validate","analyze","report","status","cleanup","package"):
        sub=subs.add_parser(name)
        sub.add_argument("--config",type=Path,default=ROOT/"configs/protocol.yaml")
        sub.add_argument("--output",type=Path)
        sub.add_argument("--dry-run",action="store_true")
        if name in ("run","pilot"):
            sub.add_argument("--resume",action="store_true")
            if name=="pilot":
                budget=sub.add_mutually_exclusive_group()
                budget.add_argument("--limit",type=int,help="maximum number of trials")
                budget.add_argument("--max-hours",type=float,help="nominal time budget; selects complete matched blocks")
            else:
                sub.add_argument("--limit",type=int,help="maximum number of trials")
        if name in ("run","pilot","estimate-matrix"):
            sub.add_argument("--study",choices=("all","primary","supplementary","robustness"),default="primary")
            sub.add_argument("--seed",type=int)
        if name in ("validate","analyze","report","package","calibrate"):
            sub.add_argument("--input",type=Path)
        if name=="analyze":sub.add_argument("--figures",action="store_true")
        if name=="test":
            g=sub.add_mutually_exclusive_group(required=True);g.add_argument("--unprivileged",action="store_true");g.add_argument("--privileged",action="store_true")
        if name=="calibrate":
            sub.add_argument("--stage",choices=("normal","cost","precision","rate","perturbation"),required=True)
            sub.add_argument("--validation",type=Path)
            sub.add_argument("--collect",action="store_true")
            sub.add_argument("--split",choices=("training","validation"),default="training")
            sub.add_argument("--limit",type=int)
            sub.add_argument("--include-io",action="store_true",help="include CPU/I/O NONE and FIX_LOW_GATE rate trials")
            sub.add_argument("--exclude-invalid",action="store_true",help="rate derivation only: omit invalid attempts and record them in the result")
        if name=="freeze":sub.add_argument("--preregistration",type=Path,default=ROOT/"state/freeze.json")
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        c=load_config(args.config)
        if getattr(args,"seed",None) is not None:c["experiment"]["seed"]=args.seed
        name=args.command
        if getattr(args,"limit",None) is not None and args.limit<1:raise ValueError("--limit must be positive")
        if name=="status":
            from .progress import render
            state=render();counts={}
            for r in state["steps"].values():counts[r["status"]]=counts.get(r["status"],0)+1
            print(json.dumps({"steps":counts,"gates":state["gates"]},indent=2));return 0
        if name=="estimate-matrix":
            from .matrix import estimate,generate
            rows=generate(c,args.study);result={"estimate":estimate(c,rows),"rows":rows}
            if args.output and not args.dry_run:write_json(args.output,result,exclusive=True)
            print(json.dumps(result["estimate"],indent=2));return 0
        if args.dry_run:
            print(json.dumps({"command":name,"config":str(args.config),"output":str(args.output) if args.output else None,
                "would_execute":describe(args,c),"dry_run":True},indent=2));return 0
        if name=="doctor":
            from .doctor import discover
            target=args.output or ROOT/"state/host.json";result=discover(target)
            print(json.dumps(result,indent=2));return 0 if result["functional_ready"] else 2
        if name=="build":
            if platform.system()!="Linux":raise ValueError("real BPF build requires Linux; portable C checks are documented separately")
            proc=subprocess.run(["make","build"],cwd=ROOT)
            return proc.returncode
        if name=="test":
            if args.privileged:
                from .privileged import run_checks
                return 0 if run_checks(c,args.output or ROOT/"state/evidence/privileged") else 2
            result=command([sys.executable,"-m","unittest","discover","-s","tests","-v"],cwd=ROOT,timeout=300)
            if args.output:write_json(args.output,result,exclusive=True)
            print(result["stdout"]+result["stderr"]);return result["returncode"]
        if name in ("run","pilot"):
            from .campaign import run_campaign
            if name=="run":
                from .freeze import verify_freeze
                verify_freeze(c,ROOT/"state/freeze.json")
            population="pilot" if name=="pilot" else "confirmatory" if args.study=="primary" else "robustness"
            result=run_campaign(c,args.output or ROOT/"data"/population,study=args.study,population=population,
                                resume=args.resume,limit=args.limit,max_hours=getattr(args,"max_hours",None))
            print(json.dumps({"rows":len(result["rows"]),"statuses":{s:sum(r["status"]==s for r in result["rows"]) for s in ("valid","failed","planned","blocked")}},indent=2));return 0
        if name=="freeze":
            from .freeze import freeze
            result=freeze(c,args.output or args.preregistration)
            print(json.dumps({"freeze_hash":result["freeze_hash"],"instruction":"Set protocol.preregistration_hash in a separate resolved config copy; retain original frozen protocol bytes."},indent=2));return 0
        if name=="validate":
            if not args.input:raise ValueError("--input attempt or campaign directory required")
            from analysis.pipeline import find_attempts
            from analysis.validate import validate_attempt
            paths=find_attempts(args.input)
            if not paths:raise ValueError("no attempt manifests")
            result=[validate_attempt(p) for p in paths]
            if args.output:write_json(args.output,result,exclusive=True)
            print(json.dumps(result,indent=2));return 0 if all(r["valid"] for r in result) else 2
        if name=="analyze":
            if not args.input:raise ValueError("--input required")
            from analysis.pipeline import analyze
            output=args.output or ROOT/"results"/c["protocol"]["version"]
            result=analyze(args.input,output,c)
            if args.figures:
                from analysis.figures import render
                render(output)
            print(json.dumps({"output":str(output),"synthetic":result["synthetic"],"comparisons":len(result["comparisons"])},indent=2));return 0
        if name=="report":
            from .report import report
            print(report(args.output or ROOT/"paper/generated",args.input));return 0
        if name=="calibrate":
            from .calibration_cli import calibrate
            print(json.dumps(calibrate(args,c),indent=2));return 0
        if name=="package":
            from .package import package
            print(json.dumps(package(args.output or ROOT/"artifact/releases",args.input),indent=2));return 0
        if name=="cleanup":
            # No global process killing, no global BPF detach, no removing unknown cgroups.
            from .cleanup import audit
            print(json.dumps(audit(args.output),indent=2));return 0
    except (ConfigError,ValueError,RuntimeError,OSError,subprocess.TimeoutExpired) as exc:
        print(f"{args.command}: {exc}",file=sys.stderr);return 2
    return 0


def describe(args,c):
    if args.command in ("run","pilot"):
        from .matrix import estimate,generate,select_within_budget
        rows=generate(c,args.study)
        if args.limit is not None:rows=rows[:args.limit]
        max_hours=getattr(args,"max_hours",None)
        if max_hours is not None:
            rows=select_within_budget(c,rows,max_hours)
            result=estimate(c,rows)
            result["max_hours_budget"]=max_hours
            result["selection_note"]="Complete matched blocks only; elapsed-time enforcement stops new attempts at trial boundaries. This subset is exploratory, not confirmatory."
            return result
        return estimate(c,rows)
    return {"doctor":"Collect platform/feature diagnostics; never treats discovery as smoke success",
            "build":"make build: target BTF,Clang BPF,skeletons,C agent/workloads",
            "test":"Run requested portable or real Linux privileged checks",
            "calibrate":"Derive training-only models/rate/storage/precision evidence; final data forbidden",
            "freeze":"Reject unresolved models/host,require clean commit and real smoke,hash registry",
            "validate":"Check schemas,seals,clocks,truth and all loss balances before metrics",
            "analyze":"First-valid attempts,paired block bootstrap,per-phase/capture/missing tables",
            "report":"Generate methods/evidence report,explicitly label absent or synthetic results",
            "cleanup":"Audit only owned recorded resources; never kill unrelated processes",
            "package":"Checksummed tracked-source/data release and archive read-back verification"}.get(args.command,args.command)
