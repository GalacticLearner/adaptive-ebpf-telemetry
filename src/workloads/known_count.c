#define _GNU_SOURCE
#include <unistd.h>
#include <sys/syscall.h>
#include <linux/futex.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include "../common/timeutil.h"
/* Target waits for runner's GO after membership registration. Never a benchmark. */
int main(int argc, char **argv) {
    if (argc != 4) { fprintf(stderr, "usage: known_count N tmpfs-file per-call.csv\n"); return 2; }
    unsigned n = strtoul(argv[1], 0, 10);
    if (!n || n > 1000000) return 2;
    int fd = open(argv[2], O_RDWR | O_CREAT, 0600);
    if (fd < 0 || ftruncate(fd, 4096)) return 2;
    FILE *log = fopen(argv[3], "wx");
    if (!log) return 2;
    fprintf(log, "entry_ns,exit_ns,syscall_id,result\n");
    printf("{\"tid\":%ld}\n", syscall(SYS_gettid)); fflush(stdout);
    char go[32], buffer[4096]; int word = 0;
    if (!fgets(go, sizeof(go), stdin)) return 2;
    for (unsigned i = 0; i < n; i++) {
        uint64_t start = aet_now();
        long result = syscall(SYS_pread64, fd, buffer, sizeof(buffer), 0);
        fprintf(log, "%llu,%llu,%d,%ld\n", (unsigned long long)start, (unsigned long long)aet_now(), SYS_pread64, result);
        start = aet_now();
        result = syscall(SYS_futex, &word, FUTEX_WAKE_PRIVATE, 1, 0, 0, 0);
        fprintf(log, "%llu,%llu,%d,%ld\n", (unsigned long long)start, (unsigned long long)aet_now(), SYS_futex, result);
    }
    /* Remain alive until detach/final counters: stable frozen membership. */
    puts("{\"done\":true}"); fflush(stdout);
    if (!fgets(go, sizeof(go), stdin)) return 2;
    fclose(log); close(fd); return 0;
}
