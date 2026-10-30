// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include "../common/wire.h"

/* mmap-backed skeleton .bss, one naturally aligned load/store on x86-64.
 * Agent rejects other architectures. Validate disassembly/load on target host. */
volatile __u64 config_word __attribute__((aligned(8)));
volatile __u32 attachment_epoch;
/* Attribution: 0=full, 1=empty, 2=filter only, 3=pair without export. */
const volatile __u32 component = 0;
struct { __uint(type, BPF_MAP_TYPE_HASH); __uint(max_entries, AET_MAX_TARGETS);
         __type(key, __u32); __type(value, __u32); } targets SEC(".maps");
struct { __uint(type, BPF_MAP_TYPE_HASH); __uint(max_entries, AET_INFLIGHT);
         __type(key, __u32); __type(value, struct aet_inflight); } inflight SEC(".maps");
struct { __uint(type, BPF_MAP_TYPE_ARRAY); __uint(max_entries, 1024);
         __type(key, __u32); __type(value, __u32); } allowlist SEC(".maps");
struct { __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY); __uint(max_entries, 1);
         __type(key, __u32); __type(value, struct aet_counters); } counters SEC(".maps");
struct { __uint(type, BPF_MAP_TYPE_RINGBUF); __uint(max_entries, 8388608); } events SEC(".maps");

static __always_inline struct aet_counters *counts(void) {
    __u32 zero = 0;
    return bpf_map_lookup_elem(&counters, &zero);
}
static __always_inline int eligible(__u32 tid, __u32 id) {
    if (!bpf_map_lookup_elem(&targets, &tid)) return 0;
    __u32 *ok = bpf_map_lookup_elem(&allowlist, &id);
    return ok && *ok;
}

SEC("tracepoint/raw_syscalls/sys_enter")
int detail_enter(struct trace_event_raw_sys_enter *ctx) {
    if (component == 1) return 0;
    __u32 tid = bpf_get_current_pid_tgid(), id = ctx->id;
    if (!eligible(tid, id) || component == 2) return 0;
    struct aet_counters *c = counts();
    if (!c) return 0;
    c->eligible++;
    /* A new eligible entry proves a stale previous selection was replaced. */
    if (bpf_map_lookup_elem(&inflight, &tid)) {
        c->replaced++;
        bpf_map_delete_elem(&inflight, &tid);
    }
    __u64 word = config_word;
    __u32 threshold = word, gen = word >> 32;
    if (!threshold || (threshold != 0xffffffffU && bpf_get_prandom_u32() >= threshold)) {
        c->rejected++; return 0;
    }
    c->selected++;
    __u32 *sequence = bpf_map_lookup_elem(&targets, &tid);
    struct aet_inflight state = { .entry_ns = bpf_ktime_get_ns(), .syscall_id = id,
        .generation = gen, .entry_cpu = bpf_get_smp_processor_id(),
        .sequence = sequence ? __sync_fetch_and_add(sequence, 1) + 1 : 0,
        .attachment_epoch = attachment_epoch };
    if (bpf_map_update_elem(&inflight, &tid, &state, BPF_NOEXIST)) c->insert_failed++;
    return 0;
}

SEC("tracepoint/raw_syscalls/sys_exit")
int detail_exit(struct trace_event_raw_sys_exit *ctx) {
    if (component == 1) return 0;
    __u64 pid = bpf_get_current_pid_tgid();
    __u32 tid = pid, id = ctx->id;
    if (!eligible(tid, id) || component == 2) return 0;
    struct aet_counters *c = counts();
    if (!c) return 0;
    struct aet_inflight *stored = bpf_map_lookup_elem(&inflight, &tid);
    if (!stored) { c->exit_without_selected++; return 0; }
    struct aet_inflight entry = *stored;
    bpf_map_delete_elem(&inflight, &tid);
    if (entry.syscall_id != id) { c->malformed++; return 0; }
    c->completed++;
    if (component == 3) return 0;
    struct aet_event *e = bpf_ringbuf_reserve(&events, sizeof(*e), 0);
    if (!e) { c->reserve_failed++; return 0; }
    *e = (struct aet_event) { .version = AET_VERSION,
        .flags = (ctx->ret <= -512 && ctx->ret >= -516) ? AET_FLAG_RESTART : 0,
        .generation = entry.generation, .entry_ns = entry.entry_ns, .exit_ns = bpf_ktime_get_ns(),
        .tgid = pid >> 32, .tid = tid, .syscall_id = id, .entry_cpu = entry.entry_cpu,
        .exit_cpu = bpf_get_smp_processor_id(), .sequence = entry.sequence, .result = ctx->ret,
        .attachment_epoch = entry.attachment_epoch };
    bpf_ringbuf_submit(e, 0);
    c->emitted++;
    return 0;
}
char LICENSE[] SEC("license") = "GPL";
