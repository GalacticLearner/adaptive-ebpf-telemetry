"""Record evidence-scoped development status without claiming Linux phase success."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runner.util import ROOT,canonical_hash,digest,git_state,read_json,utc_now,write_json
from runner.progress import render
from runner.config import load_config
from runner.matrix import generate,estimate


if __name__=="__main__":
    state=read_json(ROOT/"state/progress.json");now=utc_now();source=git_state()
    portable={"P0.2","P0.4","P1.4","P4.3","P6.2","P8.1","P9.3","P9.5"}
    literature={"P0.1","P0.3","P8.3"}
    artifacts={
        0:["context/manifest.json","configs/protocol.yaml","configs/parameter_registry.json","requirements_traceability.md","research/claims.md","research/evidence_access.csv"],
        1:["state/host.json","artifact/toolchain.lock.json","artifact/REPRODUCE.md","state/evidence/unprivileged-final-classified.json","state/evidence/c-compile-final.json"],
        2:["src/workloads/workload.c","src/workloads/known_count.c","runner/trial.py"],
        3:["src/bpf/sentinel.bpf.c","src/bpf/detail.bpf.c","src/common/wire.h","src/agent/sink.c","analysis/wire.py"],
        4:["src/common/policy.c","src/common/cost.c","src/agent/main.c","runner/reference.py","tests/test_core.py"],
        5:["runner/calibration.py","runner/calibration_cli.py","runner/collect.py","artifact/CALIBRATION.md"],
        6:["runner/matrix.py","runner/campaign.py","runner/freeze.py","state/campaign_inventory.json"],
        7:["analysis/validate.py","analysis/metrics.py","analysis/stats.py","analysis/pipeline.py","analysis/figures.py","analysis/timeline.py"],
        8:["paper/manuscript.md","paper/references.bib","paper/claim_evidence.csv","research/evidence_access.csv"],
        9:["artifact/REPRODUCE.md","runner/package.py","runner/cleanup.py","state/evidence/clean-replay.json","artifact/RELEASE.md"]}
    for step,row in state["steps"].items():
        phase=int(step[1:step.index('.')]);paths=[p for p in artifacts[phase] if (ROOT/p).exists()]
        row.update(status="done" if step in portable else "blocked",started_at=row["started_at"] or now,
            finished_at=now if step in portable else None,commit=source["commit"],artifacts=paths,
            checks=["python -m runner test --unprivileged","portable C/BPF target compile checks","synthetic sealed-attempt replay"],
            blocker=None if step in portable else "Missing v4 review/full-text audit" if step in literature else "Requires full Linux adaptive-policy transition and failure-integration evidence" if step=="P4.4" else "Requires outstanding phase-specific Linux acceptance evidence or dependent empirical evidence",
            limitations=["Done means the independent software/draft deliverable only; no kernel/performance success implied"] if step in portable else ["Sources/checks prepared; real step acceptance evidence is pending"],
            evidence_hash=canonical_hash({p:digest(ROOT/p) for p in paths}))
    state.update(source_commit=source["commit"],updated_at=now,current_phase=1)
    for phase in range(10):
        state["gates"][f"G{phase}"]={"status":"blocked","reason":
            "Scaffolding/requirements mapped; mandatory v4 source audit missing" if phase==0 else
            "Linux host discovery and privileged smoke passed; broader readiness, calibration, and performance gates remain" if phase==1 else
            "Kernel/application empirical acceptance evidence unavailable; synthetic checks do not satisfy this gate"}
    write_json(ROOT/"state/progress.json",state);render(state)
    c=load_config();rows=generate(c)
    for r in rows:r.update(status="blocked",blocker="Independent secondary Linux host required" if r["scenario"].get("host")=="secondary" else "Requires resolved calibration, protocol freeze, and confirmatory campaign")
    write_json(ROOT/"state/campaign_inventory.json",{"schema_version":1,"real_attempts":0,"valid_real_trials":0,
        "scope":"planned confirmatory registry; pilot attempts are tracked separately",
        "estimate":estimate(c,rows),"rows":rows,"calibration_excluded_from_estimate":True})
    counts={s:sum(r["status"]==s for r in state["steps"].values()) for s in ("done","doing","blocked","todo")}
    pilot=read_json(ROOT/"results/pilot/bounded-q01-4blocks-20261114-001/results.json")
    pilot_attempts=pilot.get("attempts",[])
    write_json(ROOT/"state/status_summary.json",{"steps":counts,"gates_passed":0,"gates_total":10,
        "code_status":"Linux build and privileged smoke passed; validated pilot attempts retained; confirmatory matrix pending",
        "pilot_trials":{"valid":sum(bool(a.get("valid")) for a in pilot_attempts),"total":len(pilot_attempts),
            "noise_flagged":sum(bool(a.get("warnings")) for a in pilot_attempts)},
        "real_primary_trials":{"valid":0,"planned":672,"scope":"confirmatory matrix; pilot excluded"},
        "real_all_registry_trials":{"valid":0,"planned":len(rows),"scope":"confirmatory registry; pilot excluded"},
        "research_conclusion":"Pilot results are exploratory; adaptive-policy and formal budget conclusions remain inconclusive"})
    print(counts)
