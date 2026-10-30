"""One-time, idempotent preservation of supplied context and plan step IDs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner.util import ROOT, utc_now, write_json


def main():
    for name in ("context", "state/evidence", "src/bpf", "src/common", "src/agent", "src/workloads",
                 "tests", "schemas", "paper", "artifact", "results", "data/synthetic", "data/calibration",
                 "data/pilot", "data/confirmatory", "data/robustness"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    entries = []
    for source in sorted((ROOT / "research").iterdir()):
        if source.name not in ("plan.md", "eBPF_OS_Assignment_4_Resource-Aware_eBPF_Observability.docx",
                               "eBPF_Observability_Literature_Review_2026-10-29.md",
                               "novelty_review_v3.md", "novelty_review_v4.md", "adaptive_ebpf_research.zip"):
            continue
        target = ROOT / "context" / source.name
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != source_hash:
            raise RuntimeError(f"preserved context differs: {target}")
        if not target.exists():
            shutil.copy2(source, target)
        entries.append({"path": str(target.relative_to(ROOT)), "sha256": source_hash,
                        "source": str(source.relative_to(ROOT)), "retrieved_at": utc_now()})
    manifest = ROOT / "context/manifest.json"
    if not manifest.exists():
        write_json(manifest, {"schema_version": 1, "sources": entries,
                   "missing": [p for p in ("novelty_review_v3.md", "novelty_review_v4.md", "adaptive_ebpf_research.zip")
                               if not (ROOT / "research" / p).exists()]}, exclusive=True)
    assignment = ROOT / "context/assignment.txt"
    if not assignment.exists():
        with zipfile.ZipFile(ROOT / "context/eBPF_OS_Assignment_4_Resource-Aware_eBPF_Observability.docx") as archive:
            tree = ET.fromstring(archive.read("word/document.xml"))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        assignment.write_text("\n".join("".join(p.itertext()) for p in tree.findall(".//w:p", ns)), encoding="utf-8")
    progress = ROOT / "state/progress.json"
    if not progress.exists():
        steps = {}
        last_phase = []
        plan = (ROOT / "context/plan.md").read_text(encoding="utf-8")
        for phase in range(10):
            group = []
            for step, title in re.findall(r"\*\*(P" + str(phase) + r"\.\d+) — (.*?)\.\*\*", plan):
                steps[step] = {"title": title, "status": "todo", "depends_on": last_phase.copy(),
                               "artifacts": [], "checks": [], "blocker": None, "started_at": None,
                               "finished_at": None, "commit": None, "evidence_hash": None, "limitations": []}
                group.append(step)
            last_phase = group
        write_json(progress, {"schema_version": 1, "protocol_version": "aet-v1", "source_commit": None,
                             "updated_at": utc_now(), "current_phase": 0, "gates": {}, "steps": steps}, exclusive=True)
    for population in ("synthetic", "calibration", "pilot", "confirmatory", "robustness"):
        (ROOT / "data" / population / ".gitkeep").touch(exist_ok=True)
    (ROOT / "results/.gitkeep").touch(exist_ok=True)
    print(f"Preserved {len(entries)} sources; {len(json.loads(progress.read_text())['steps'])} plan steps registered")


if __name__ == "__main__":
    main()
