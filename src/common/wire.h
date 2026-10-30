/* SPDX-License-Identifier: MIT */
#ifndef AET_WIRE_H
#define AET_WIRE_H
#ifndef __VMLINUX_H__
#ifdef __linux__
#include <linux/types.h>
#else
#include <stdint.h>
typedef uint64_t __u64;
typedef int64_t __s64;
typedef uint32_t __u32;
typedef uint16_t __u16;
#endif
#endif

#define AET_VERSION 1
#define AET_BINS 2048
#define AET_BIN_NS 5000000ULL
#define AET_EMPTY_EPOCH (~0ULL)
#define AET_MAX_TARGETS 128
#define AET_INFLIGHT 8192

struct aet_event {
    __u16 version, flags;
    __u32 generation;
    __u64 entry_ns, exit_ns;
    __u32 tgid, tid, syscall_id, entry_cpu, exit_cpu, sequence;
    __s64 result;
    __u32 attachment_epoch, reserved;
};
_Static_assert(sizeof(struct aet_event) == 64, "event ABI must be 64 bytes");
_Static_assert(__builtin_offsetof(struct aet_event, entry_ns)==8, "entry offset");
_Static_assert(__builtin_offsetof(struct aet_event, result)==48, "return offset");
_Static_assert(__builtin_offsetof(struct aet_event, attachment_epoch)==56, "attachment offset");

struct aet_inflight {
    __u64 entry_ns;
    __u32 syscall_id, generation, entry_cpu, sequence, attachment_epoch, pad;
};
struct aet_bin { __u64 seq, epoch, count; };
struct aet_counters {
    __u64 eligible, rejected, selected, insert_failed, replaced, malformed;
    __u64 exit_without_selected, completed, reserve_failed, emitted;
};
enum aet_mode { AET_LOW, AET_MEDIUM, AET_HIGH };
/* Restart return values are retained in result; flags are transport metadata. */
#define AET_FLAG_RESTART 1
#endif
