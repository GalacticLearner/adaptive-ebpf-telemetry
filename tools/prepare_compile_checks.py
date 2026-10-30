"""Development-only headers for cross syntax checks; NEVER a privileged/BPF pass."""
from pathlib import Path
import tarfile
import hashlib

build=Path("build")
archive=build/"libbpf-v1.5.1.tar.gz"
expected="e5ff89750e48ab5ecdfc02a759aa0dacd1e7980e98e16bdb4bfa8ff0b3b4b98f"
if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:
    raise SystemExit("libbpf source checksum mismatch")
with tarfile.open(archive) as tar:
    tar.extractall(build, filter="data")
include=build/"check-include"
(include/"bpf").mkdir(parents=True,exist_ok=True)
import shutil
for p in (build/"libbpf-1.5.1/src").glob("*.h"):
    shutil.copy2(p,include/"bpf"/p.name)
for name, maps, programs, globals_ in [
    ("sentinel",["targets","bins","totals"],["sentinel_switch"],""),
    ("detail",["targets","inflight","allowlist","counters","events"],["detail_enter","detail_exit"],
     "struct { volatile unsigned long long config_word; volatile unsigned attachment_epoch; } *bss; struct { unsigned component; } *rodata;")]:
    text="#include <bpf/libbpf.h>\n"
    text+=f"struct {name}_bpf {{ struct {{"+"".join(f"struct bpf_map *{m};" for m in maps)+"} maps; struct {"+"".join(f"struct bpf_program *{p};" for p in programs)+"} progs;"+globals_+"};\n"
    text+=f"struct {name}_bpf *{name}_bpf__open(void); int {name}_bpf__load(struct {name}_bpf*); void {name}_bpf__destroy(struct {name}_bpf*);\n"
    (include/f"{name}.skel.h").write_text(text)
# Minimal type surface for compile diagnostics only; real builds generate vmlinux.h from host BTF.
(include/"vmlinux.h").write_text('''#ifndef __VMLINUX_H__
#define __VMLINUX_H__
#include <linux/types.h>
#include <linux/bpf.h>
struct trace_event_raw_sched_switch { unsigned long long pad; char prev_comm[16]; int prev_pid, prev_prio; long prev_state; char next_comm[16]; int next_pid, next_prio; };
struct trace_event_raw_sys_enter { unsigned long long pad; long id; unsigned long args[6]; };
struct trace_event_raw_sys_exit { unsigned long long pad; long id,ret; };
#endif
''')
print("Development syntax-check headers prepared; not load/CO-RE verification")
