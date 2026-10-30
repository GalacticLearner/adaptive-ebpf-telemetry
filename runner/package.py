from __future__ import annotations

import hashlib
from pathlib import Path
import tarfile

from .util import ROOT, command, digest, git_state, read_json, utc_now, write_json


def package(output, data=None):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    state=git_state()
    if not state["commit"]:raise ValueError("commit source before packaging")
    tarpath=output/f"aet-{state['commit'][:12]}.tar.gz"
    if tarpath.exists():raise ValueError("release already exists; never overwrite a release")
    names=[n for n in command(["git","ls-files","-z"],cwd=ROOT)["stdout"].split("\0") if n]
    files={n:digest(ROOT/n) for n in names if (ROOT/n).is_file()}
    raw=[]
    if data:
        data=Path(data).resolve()
        if not data.is_relative_to((ROOT/"data").resolve()):raise ValueError("only project data may be packaged")
        for p in data.rglob("*"):
            if p.is_file():
                rel=p.relative_to(ROOT).as_posix();files[rel]=digest(p);raw.append(rel)
    manifest={"schema_version":1,"created":utc_now(),"source":state,"files":files,
              "data_files":raw,"missing_experiments":"see PROGRESS.md and campaign inventories"}
    with tarfile.open(tarpath,"w:gz",format=tarfile.PAX_FORMAT) as archive:
        for name in sorted(files):archive.add(ROOT/name,arcname=name,recursive=False)
    # Read back the bundle and verify every stored byte rather than only successful creation.
    with tarfile.open(tarpath) as archive:
        for member in archive.getmembers():
            f=archive.extractfile(member)
            if not f or hashlib.sha256(f.read()).hexdigest()!=files[member.name]:raise ValueError("release restore verification failed")
    manifest["archive_sha256"]=digest(tarpath)
    write_json(output/f"{tarpath.name}.manifest.json",manifest,exclusive=True)
    return {"path":str(tarpath),"sha256":manifest["archive_sha256"],"files":len(files)}
