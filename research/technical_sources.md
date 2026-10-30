# Implementation sources

Access checked 2026-10-30. These are semantic references, not evidence that this implementation has loaded successfully.

- [libbpf overview](https://docs.kernel.org/bpf/libbpf/libbpf_overview.html): open/load/attach/teardown, generated skeletons and CO-RE.
- [BPF ring buffer](https://docs.kernel.org/bpf/ringbuf.html): reservation failure and transport semantics; ring capacity is a power of two.
- [BTF](https://docs.kernel.org/bpf/btf.html): target-kernel type information and endianness.
- [cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html): process hierarchy and accounting.
- [libbpf v1.5.1 source](https://github.com/libbpf/libbpf/tree/v1.5.1): exact APIs used by the cross-compilation checks. Archive SHA-256: `e5ff89750e48ab5ecdfc02a759aa0dacd1e7980e98e16bdb4bfa8ff0b3b4b98f`.

Naturally aligned mapped 64-bit configuration publication is restricted to little-endian x86-64. Generated BPF instruction inspection, target load and concurrency tests remain mandatory; a successful development-header compile is insufficient.
