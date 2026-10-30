# Exact next action

On an authorized Ubuntu24.04 x86-64 Linux host after transferring this repository:

```bash
bash artifact/bootstrap-linux.sh
```

Expected output: exact package resolution and installed versions under `state/bootstrap/`, verified libbpf1.5.1 archive, generated target BTF/skeletons, compiled agent/workloads/controller checks, and the next doctor command. The script changes no kernel, boot or security policy.

Then run the doctor, configure a real host/candidate config and execute the privileged count/cleanup smoke exactly as shown in `artifact/REPRODUCE.md`. Expected smoke: q=1 produces exactly2,000 eligible/selected/completed/received pairs for1,000 explicit pread+futex iterations, q=0/SENT selects zero, and owned program inventory returns to baseline.

No Linux access decision is required now. All real experiment rows remain explicitly blocked. The other missing input is the plan's `novelty_review_v4.md`; its audit cannot be fabricated.
