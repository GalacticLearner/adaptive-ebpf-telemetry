// SPDX-License-Identifier: GPL-2.0
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include "../common/wire.h"

struct { __uint(type, BPF_MAP_TYPE_HASH); __uint(max_entries, AET_MAX_TARGETS);
         __type(key, __u32); __type(value, __u32); } targets SEC(".maps");
struct { __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY); __uint(max_entries, AET_BINS);
         __type(key, __u32); __type(value, struct aet_bin); } bins SEC(".maps");
struct { __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY); __uint(max_entries, 1);
         __type(key, __u32); __type(value, __u64); } totals SEC(".maps");

SEC("tracepoint/sched/sched_switch")
int sentinel_switch(struct trace_event_raw_sched_switch *ctx) {
    __u32 prev = ctx->prev_pid, next = ctx->next_pid;
    if (!bpf_map_lookup_elem(&targets, &prev) && !bpf_map_lookup_elem(&targets, &next)) return 0;
    __u64 epoch = bpf_ktime_get_ns() / AET_BIN_NS;
    __u32 index = epoch % AET_BINS, zero = 0;
    struct aet_bin *bin = bpf_map_lookup_elem(&bins, &index);
    __u64 *total = bpf_map_lookup_elem(&totals, &zero);
    if (bin) {
        /* A per-CPU sched_switch writer cannot migrate. Sequence protects snapshots. */
        __sync_fetch_and_add(&bin->seq, 1);
        if (bin->epoch != epoch) { bin->count = 0; bin->epoch = epoch; }
        bin->count++;
        __sync_fetch_and_add(&bin->seq, 1);
    }
    if (total) (*total)++;
    return 0;
}
char LICENSE[] SEC("license") = "GPL";
