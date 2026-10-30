#ifndef AET_TIMEUTIL_H
#define AET_TIMEUTIL_H
#include <stdint.h>
#include <time.h>
#include <errno.h>
static inline uint64_t aet_now(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000000ULL + t.tv_nsec;
}
static inline int aet_sleep_until(uint64_t ns) {
    struct timespec t = { .tv_sec = ns / 1000000000ULL, .tv_nsec = ns % 1000000000ULL };
    int rc;
    do { rc = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &t, 0); } while (rc == EINTR);
    return rc;
}
static inline uint64_t aet_mix(uint64_t x) {
    x += 0x9e3779b97f4a7c15ULL;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
    return x ^ (x >> 31);
}
#endif
