from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil

from .util import command, utc_now, write_json


def _read(path):
    try:
        return Path(path).read_text().strip()
    except (OSError, UnicodeError):
        return None


def discover(output=None):
    linux = platform.system() == "Linux"
    host = {"schema_version": 1, "observed_at": utc_now(), "system": platform.system(),
            "kernel": platform.release(), "machine": platform.machine(), "host": platform.node(),
            "python": platform.python_version(), "cpu_count": os.cpu_count(), "clock": "CLOCK_MONOTONIC",
            "privileged_smoke_passed": False, "functional_ready": False, "performance_ready": False,
            "blockers": [], "tools": {}, "features": {}, "topology": [],
            "disk": dict(zip(("total", "used", "free"), shutil.disk_usage(Path.cwd())))}
    for tool in ("clang", "cc", "bpftool", "pkg-config", "make", "git"):
        path = shutil.which(tool)
        if tool == "clang" and not path:
            path = shutil.which("clang-18")
        host["tools"][tool] = command([path, "version" if tool == "bpftool" else "--version"], timeout=10) if path else None
    if not linux:
        host["blockers"].append("Linux tracing host unavailable; no BPF feature/load/attach evidence")
        if platform.system() == "Windows" and shutil.which("wsl"):
            host["wsl"] = command(["wsl", "--status"], timeout=15)
            for field in ("stdout","stderr"):host["wsl"][field]=host["wsl"][field].replace("\x00","")
        if output:
            write_json(output, host)
            Path(output).with_suffix(".log").write_text(f"Platform: {host['system']} {host['kernel']}\nFunctional ready: false\n"+"\n".join(host["blockers"])+"\n",encoding="utf-8")
        return host
    host["boot_id"] = _read("/proc/sys/kernel/random/boot_id")
    host["host_id"] = _read("/etc/machine-id")
    host["os_release"] = _read("/etc/os-release")
    host["kernel_config"] = _read(f"/boot/config-{platform.release()}")
    host["memory"] = _read("/proc/meminfo")
    host["pressure"] = {n: _read(f"/proc/pressure/{n}") for n in ("cpu", "memory", "io")}
    host["lockdown"] = _read("/sys/kernel/security/lockdown")
    host["capabilities"] = _read("/proc/self/status")
    host["cgroup"] = _read("/proc/self/cgroup")
    host["cpu_stat"] = _read("/proc/stat")
    host["processes"] = command(["ps", "-eo", "pid,comm,pcpu,psr"], timeout=10)
    host["clock_sync"] = command(["timedatectl", "show"], timeout=10) if shutil.which("timedatectl") else None
    host["hypervisor"] = command(["systemd-detect-virt"], timeout=10) if shutil.which("systemd-detect-virt") else None
    host["features"]["btf"] = Path("/sys/kernel/btf/vmlinux").is_file()
    host["features"]["cgroup_v2"] = Path("/sys/fs/cgroup/cgroup.controllers").is_file()
    root = next((p for p in (Path("/sys/kernel/tracing"), Path("/sys/kernel/debug/tracing")) if (p / "events").exists()), Path("/sys/kernel/tracing"))
    for name, trace in (("sched_switch", "sched/sched_switch"), ("sys_enter", "raw_syscalls/sys_enter"), ("sys_exit", "raw_syscalls/sys_exit")):
        host["features"][name] = (root / "events" / trace / "format").is_file()
        host[name + "_format"] = _read(root / "events" / trace / "format")
    physical = {}
    allowed = os.sched_getaffinity(0)
    for p in sorted(Path("/sys/devices/system/cpu").glob("cpu[0-9]*"), key=lambda p: int(p.name[3:])):
        cpu = int(p.name[3:])
        if cpu not in allowed:
            continue
        core, package = _read(p / "topology/core_id"), _read(p / "topology/physical_package_id")
        host["topology"].append({"cpu": cpu, "core": core, "package": package,
                                 "siblings": _read(p / "topology/thread_siblings_list"),
                                 "governor": _read(p / "cpufreq/scaling_governor"),
                                 "frequency_khz": _read(p / "cpufreq/scaling_cur_freq")})
        physical.setdefault((package, core), cpu)
    host["suggested_cpus"] = list(physical.values())[:4]
    if host["tools"]["bpftool"]:
        host["feature_probe"] = command(["bpftool", "-j", "feature", "probe", "kernel"], timeout=30)
    for feature, present in host["features"].items():
        if not present:
            host["blockers"].append(f"missing {feature}")
    for tool in ("clang", "cc", "bpftool", "pkg-config", "make"):
        if not host["tools"][tool]:
            host["blockers"].append(f"missing tool: {tool}")
    if platform.machine() != "x86_64":
        host["blockers"].append("unsupported syscall/config publication architecture")
    if len(physical) < 4:
        host["blockers"].append("fewer than four distinct allowed physical cores")
    host["blockers"].append("real privileged smoke/count/cleanup tests have not yet passed")
    if output:
        write_json(output, host)
        Path(output).with_suffix(".log").write_text(f"Kernel:{host['kernel']}\nPrivileged smoke: not yet passed\n"+"\n".join(host["blockers"])+"\n",encoding="utf-8")
    return host
