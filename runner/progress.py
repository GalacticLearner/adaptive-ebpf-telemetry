from __future__ import annotations

from pathlib import Path

from .util import ROOT, canonical_hash, digest, git_state, read_json, utc_now, write_json

VALID = {"todo", "doing", "blocked", "done", "skipped-with-reason"}


def update(step, status, *, artifacts=(), checks=(), blocker=None, limitations=()):
    if status not in VALID:
        raise ValueError(status)
    path=ROOT/"state/progress.json"
    state=read_json(path)
    row=state["steps"][step]
    if not row["started_at"]:row["started_at"]=utc_now()
    evidence={str(p):digest(ROOT/p) for p in artifacts if (ROOT/p).is_file()}
    row.update(status=status,artifacts=list(artifacts),checks=list(checks),blocker=blocker,
               finished_at=utc_now() if status=="done" else None,commit=git_state()["commit"],
               evidence_hash=canonical_hash(evidence),limitations=list(limitations))
    state["updated_at"]=utc_now();state["source_commit"]=git_state()["commit"]
    write_json(path,state)
    render(state)


def render(state=None):
    state=state or read_json(ROOT/"state/progress.json")
    lines=["# Plan progress", "", f"Updated: {state['updated_at']}", "",
           "Status reflects evidence, not source-code presence. Windows cannot satisfy Linux kernel/performance gates.", ""]
    for phase in range(10):
        lines.extend([f"## Phase {phase}","","| Step | Status | Work / blocker |","|---|---|---|"])
        for key,row in state["steps"].items():
            if key.startswith(f"P{phase}."):
                text=row["title"]+(" — "+row["blocker"] if row["blocker"] else "")
                lines.append(f"| {key} | {row['status']} | {text} |")
        gate=state.get("gates",{}).get(f"G{phase}",{})
        lines.extend(["",f"Gate G{phase}: {gate.get('status','not passed')}. {gate.get('reason','Evidence pending.')}",""])
    (ROOT/"PROGRESS.md").write_text("\n".join(lines),encoding="utf-8")
    return state
