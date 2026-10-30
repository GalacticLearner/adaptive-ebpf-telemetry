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
            blocker=None if step in portable else "Missing v4 review/full-text audit" if step in literature else "Latest native C execution blocked by Windows Application Control; real integration also requires Linux" if step=="P4.4" else "Requires real authorized Linux/kernel measurements or dependent empirical evidence",
            limitations=["Done means the independent software/draft deliverable only; no kernel/performance success implied"] if step in portable else ["Sources/checks prepared; real step acceptance evidence is pending"],
            evidence_hash=canonical_hash({p:digest(ROOT/p) for p in paths}))
    state.update(source_commit=source["commit"],updated_at=now,current_phase=1)
    for phase in range(10):
        state["gates"][f"G{phase}"]={"status":"blocked","reason":
            "Scaffolding/requirements mapped; mandatory v4 source audit missing" if phase==0 else
            "Linux host explicitly unavailable; portable fallback complete" if phase==1 else
            "Kernel/application empirical acceptance evidence unavailable; synthetic checks do not satisfy this gate"}
    write_json(ROOT/"state/progress.json",state);render(state)
    c=load_config();rows=generate(c)
    for r in rows:r.update(status="blocked",blocker="independent secondary Linux host unavailable" if r["scenario"].get("host")=="secondary" else "primary Linux test host unavailable")
    write_json(ROOT/"state/campaign_inventory.json",{"schema_version":1,"real_attempts":0,"valid_real_trials":0,
        "estimate":estimate(c,rows),"rows":rows,"calibration_excluded_from_estimate":True})
    counts={s:sum(r["status"]==s for r in state["steps"].values()) for s in ("done","doing","blocked","todo")}
    write_json(ROOT/"state/status_summary.json",{"steps":counts,"gates_passed":0,"gates_total":10,
        "code_status":"host-independent implementation checked; Linux execution and empirical validation pending",
        "real_primary_trials":{"valid":0,"planned":672},"real_all_registry_trials":{"valid":0,"planned":len(rows)},
        "research_conclusion":"No empirical hypothesis support or publication-readiness claim"})
    print(counts)
