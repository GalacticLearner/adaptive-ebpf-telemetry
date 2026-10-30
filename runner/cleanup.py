from __future__ import annotations

from pathlib import Path
import platform

from .util import ROOT, command, read_json, write_json


def audit(output=None):
    if platform.system()!="Linux":
        result={"schema_version":1,"host_cleanup_verified":False,"reason":"no Linux instrumentation was started here","owned_active_processes":[]}
    else:
        result={"schema_version":1,"host_cleanup_verified":False,"inventory":{k:command(["bpftool","-j",k,"show"],timeout=15) for k in ("link","map","prog")},
                "owned_cgroups":[str(p) for p in Path("/sys/fs/cgroup").glob("aet-*")],
                "owned_staging":[str(p) for p in Path("/dev/shm").glob("aet-*")],
                "note":"Audit only. Unrecorded ownership is not authority to kill/delete resources. Review per-attempt cleanup.json and program/link IDs."}
        result["host_cleanup_verified"]=not result["owned_cgroups"] and not result["owned_staging"]
    if output:write_json(output,result,exclusive=True)
    return result
