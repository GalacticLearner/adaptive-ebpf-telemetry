// SPDX-License-Identifier: MIT
#define _GNU_SOURCE
#include <stdatomic.h>
#include <pthread.h>
#include <sched.h>
#include <signal.h>
#include <sys/syscall.h>
#include <sys/resource.h>
#include <sys/prctl.h>
#include <linux/futex.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include "../common/timeutil.h"

#define MAX_EPISODES 64
#define SAMPLE_CAP 200000
struct sample { uint64_t ns, successful, attempted, short_reads, failed, checksum; int phase; };
struct episode {
    unsigned id, kind, duration_ms;
    uint64_t offset_ns, barrier_ns, end_ns;
    struct { uint64_t calls, waits, wakes, errors, interrupted, first_ns, last_ns, checksum; } helper[2];
};
struct worker { int role, tid, cpu, fd; pthread_t thread; struct sample *samples; size_t count; uint64_t histogram[64], hist_n; };
static struct worker workers[6];
static struct episode episodes[MAX_EPISODES];
static unsigned n_episodes, repeats, duration_s, warmup_s, drift_at_s, sample_every;
static int io_mode, drift, high_background, cpus[4], truth_aggregation=1;
static uint64_t seed, epoch_ns, stop_ns, background_cpu_ns;
static _Atomic int ready, launched, terminating, current_episode = -1, episode_stop, episode_done, turn;
static pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t condition = PTHREAD_COND_INITIALIZER;
static volatile sig_atomic_t interrupted;

static void signal_stop(int sig) { (void)sig; interrupted = 1; }
static void sleep_interruptible(uint64_t until) {
    while(!interrupted) {
        uint64_t now=aet_now();if(now>=until)break;
        aet_sleep_until(until-now>10000000ULL?now+10000000ULL:until);
    }
}
static void die(const char *message) { perror(message); exit(2); }
static uint64_t compute(uint64_t value, unsigned count) {
    /* One frozen repeat hashes a private fixed-size (512-byte) logical buffer. */
    uint64_t buffer[64];
    for (unsigned i = 0; i < 64; i++) buffer[i] = aet_mix(value + i);
    for (unsigned r = 0; r < count; r++)
        for (unsigned i = 0; i < 64; i++) buffer[i] = aet_mix(buffer[i] ^ buffer[(i + 31) % 64]);
    for (unsigned i = 0; i < 64; i++) value ^= buffer[i];
    return value;
}
static void pin(int cpu) {
    cpu_set_t mask; CPU_ZERO(&mask); CPU_SET(cpu, &mask);
    int rc = pthread_setaffinity_np(pthread_self(), sizeof(mask), &mask);
    if (rc) { errno = rc; die("affinity"); }
}
static void register_thread(struct worker *w) {
    pin(w->cpu); w->tid = syscall(SYS_gettid);
    atomic_fetch_add(&ready, 1);
    pthread_mutex_lock(&mutex);
    while (!atomic_load(&launched) && !atomic_load(&terminating)) pthread_cond_wait(&condition, &mutex);
    pthread_mutex_unlock(&mutex);
}
static void append(struct worker *w, struct sample *s, uint64_t ns, int phase) {
    if (w->count >= SAMPLE_CAP) { atomic_store(&terminating, 1); return; }
    s->ns = ns; s->phase = phase; w->samples[w->count++] = *s;
}
static void *benchmark(void *arg) {
    struct worker *w = arg;
    register_thread(w);
    if (atomic_load(&terminating)) return NULL;
    uint64_t start = epoch_ns - (uint64_t)warmup_s * 1000000000ULL;
    aet_sleep_until(start);
    struct sample s = {0}; unsigned char buffer[16384];
    uint64_t next_publish = start, index = seed + w->role, now = aet_now();
    while (!atomic_load(&terminating) && now < stop_ns) {
        int phase = drift && now >= epoch_ns + (uint64_t)drift_at_s * 1000000000ULL;
        unsigned size = phase ? 16384 : 4096;
        int good = 1;
        uint64_t unit_start = sample_every && s.attempted % sample_every == 0 ? aet_now() : 0;
        if (io_mode) {
            off_t offset = (off_t)((aet_mix(index) % (67108864ULL / 16384)) * 16384);
            long got = syscall(SYS_pread64, w->fd, buffer, size, offset);
            if (got < 0) { s.failed++; good = 0; }
            else if ((unsigned)got != size) { s.short_reads++; good = 0; }
            else s.checksum ^= buffer[aet_mix(index) % size];
        }
        s.checksum ^= compute(index++, repeats * ((!io_mode && phase) ? 2 : 1));
        s.attempted++; s.successful += good;
        now = aet_now();
        if (unit_start) {
            uint64_t elapsed = now - unit_start; unsigned bin = 0;
            while (elapsed > 1 && bin < 63) { bin++; elapsed >>= 1; }
            w->histogram[bin]++; w->hist_n++;
        }
        if (now >= next_publish) {
            append(w, &s, now, phase); next_publish = now + 100000000ULL;
        }
    }
    append(w, &s, aet_now(), drift && aet_now() >= epoch_ns + (uint64_t)drift_at_s * 1000000000ULL);
    /* Park with stable TID until runner has stopped the agent. */
    pthread_mutex_lock(&mutex);
    while (!atomic_load(&terminating)) pthread_cond_wait(&condition, &mutex);
    pthread_mutex_unlock(&mutex);
    return NULL;
}
static void *incident_helper(void *arg) {
    struct worker *w = arg; int logical = w->role - 2, seen = -1;
    register_thread(w);
    while (!atomic_load(&terminating)) {
        pthread_mutex_lock(&mutex);
        while (atomic_load(&current_episode) == seen && !atomic_load(&terminating))
            pthread_cond_wait(&condition, &mutex);
        int index = atomic_load(&current_episode);
        pthread_mutex_unlock(&mutex);
        if (atomic_load(&terminating)) break;
        seen = index;
        if (index < 0 || episodes[index].kind != 0) continue;
        struct episode *e = &episodes[index];
        while (!atomic_load(&episode_stop) && !atomic_load(&terminating)) {
            struct timespec timeout = {.tv_sec = 0, .tv_nsec = 1000000};
            int value = atomic_load(&turn), result;
            uint64_t before = aet_now();
            if (!e->helper[logical].first_ns) e->helper[logical].first_ns = before;
            if (value == logical) {
                atomic_store(&turn, 1 - logical);
                result = syscall(SYS_futex, &turn, FUTEX_WAKE_PRIVATE, 1, 0, 0, 0);
                if(truth_aggregation)e->helper[logical].wakes++;
            } else {
                result = syscall(SYS_futex, &turn, FUTEX_WAIT_PRIVATE, value, &timeout, 0, 0);
                if(truth_aggregation)e->helper[logical].waits++;
            }
            if(truth_aggregation){e->helper[logical].last_ns = aet_now(); e->helper[logical].calls++;}
            if (truth_aggregation && result < 0) {
                e->helper[logical].errors++;
                e->helper[logical].interrupted += errno == EINTR;
            }
            if(truth_aggregation)e->helper[logical].checksum ^= aet_mix(e->helper[logical].calls + logical);
        }
        if(!truth_aggregation)e->helper[logical].last_ns=aet_now();
        atomic_fetch_add(&episode_done, 1);
    }
    return NULL;
}
static void *contention(void *arg) {
    struct worker *w = arg; int seen = -1; register_thread(w); uint64_t checksum = seed;
    while (!atomic_load(&terminating)) {
        pthread_mutex_lock(&mutex);
        while (atomic_load(&current_episode) == seen && !atomic_load(&terminating)) pthread_cond_wait(&condition, &mutex);
        int index = atomic_load(&current_episode); pthread_mutex_unlock(&mutex);
        if (atomic_load(&terminating)) break;
        seen = index;
        if (index < 0 || episodes[index].kind != 1) continue;
        struct episode *e = &episodes[index];
        e->helper[0].first_ns = aet_now();
        while (!atomic_load(&episode_stop) && !atomic_load(&terminating)) checksum = compute(checksum, 4);
        e->helper[0].last_ns = aet_now(); e->helper[0].checksum = checksum;
        atomic_fetch_add(&episode_done, 1);
    }
    return NULL;
}
static void *background(void *arg) {
    struct worker *w = arg; register_thread(w);
    struct timespec t; clock_gettime(CLOCK_THREAD_CPUTIME_ID, &t);
    uint64_t begin = (uint64_t)t.tv_sec * 1000000000ULL + t.tv_nsec, checksum = seed;
    uint64_t next = aet_now();
    while (!atomic_load(&terminating) && aet_now() < stop_ns) {
        if (high_background) {
            while (aet_now() < next + 5000000ULL && !atomic_load(&terminating)) checksum = compute(checksum, 1);
        }
        next += 10000000ULL; aet_sleep_until(next);
    }
    clock_gettime(CLOCK_THREAD_CPUTIME_ID, &t);
    background_cpu_ns = (uint64_t)t.tv_sec * 1000000000ULL + t.tv_nsec - begin;
    return (void *)(uintptr_t)checksum;
}
static void prepare_file(struct worker *w, const char *directory) {
    char name[4096]; snprintf(name, sizeof(name), "%s/io-%d.bin", directory, w->role);
    w->fd = open(name, O_RDWR | O_CREAT | O_EXCL, 0600);
    if (w->fd < 0) die("create tmpfs IO file");
    if (unlink(name)) die("unlink owned tmpfs file");
    unsigned char block[16384];
    for (unsigned offset = 0; offset < 67108864; offset += sizeof(block)) {
        if(interrupted){close(w->fd);exit(130);}
        for (unsigned i = 0; i < sizeof(block); i++) block[i] = aet_mix(seed + w->role + offset + i);
        if (write(w->fd, block, sizeof(block)) != sizeof(block)) die("prefault tmpfs file");
    }
    /* Owned file persists through all reads, then is automatically reclaimed. */
}
static void save(const char *output, uint64_t measured_end) {
    char name[4096]; snprintf(name, sizeof(name), "%s/app.csv", output);
    FILE *f = fopen(name, "wx"); if (!f) die("app.csv");
    fprintf(f, "monotonic_ns,worker,phase,successful,attempted,short_reads,failed,checksum\n");
    for (unsigned w = 0; w < 2; w++) for (size_t i = 0; i < workers[w].count; i++) {
        struct sample *s = &workers[w].samples[i];
        fprintf(f, "%"PRIu64",%u,%d,%"PRIu64",%"PRIu64",%"PRIu64",%"PRIu64",%"PRIu64"\n",
            s->ns,w,s->phase,s->successful,s->attempted,s->short_reads,s->failed,s->checksum);
    }
    fclose(f);
    snprintf(name, sizeof(name), "%s/truth.jsonl", output); f = fopen(name, "wx"); if (!f) die("truth.jsonl");
    fprintf(f, "{\"type\":\"epoch\",\"start_ns\":%"PRIu64",\"end_ns\":%"PRIu64",\"clock\":\"CLOCK_MONOTONIC\"}\n", epoch_ns, measured_end);
    if (drift) fprintf(f, "{\"type\":\"drift\",\"start_ns\":%"PRIu64"}\n", (uint64_t)(epoch_ns + (uint64_t)drift_at_s * 1000000000ULL));
    fprintf(f, "{\"type\":\"background\",\"high\":%s,\"cpu_ns\":%"PRIu64"}\n", high_background ? "true" : "false", background_cpu_ns);
    for (unsigned i = 0; i < n_episodes; i++) {
        struct episode *e = &episodes[i]; uint64_t start = e->barrier_ns, end = start, calls = 0;
        unsigned helpers = e->kind == 0 ? 2 : 1;
        for (unsigned h = 0; h < helpers; h++) {
            if (e->helper[h].last_ns > end) end = e->helper[h].last_ns;
            calls += e->helper[h].calls;
        }
        fprintf(f, "{\"type\":\"episode\",\"episode_id\":%u,\"kind\":\"%s\",\"nominal_ms\":%u,\"intended_ns\":%"PRIu64",\"start_ns\":%"PRIu64",\"end_ns\":%"PRIu64",\"eligible_calls\":%"PRIu64",\"valid\":%s,\"helpers\":[",
            e->id, e->kind == 0 ? "futex" : "cpu", e->duration_ms, epoch_ns + e->offset_ns, start, end, calls,
            start && end > start && (e->kind || calls || !truth_aggregation) ? "true" : "false");
        for (unsigned h = 0; h < helpers; h++) fprintf(f,
            "%s{\"role\":\"%s%u\",\"tid\":%d,\"first_ns\":%"PRIu64",\"last_ns\":%"PRIu64",\"calls\":%"PRIu64",\"waits\":%"PRIu64",\"wakes\":%"PRIu64",\"errors\":%"PRIu64",\"interrupted\":%"PRIu64",\"checksum\":%"PRIu64"}",
            h ? "," : "", e->kind ? "contention" : "futex", h, workers[e->kind ? 4 : h + 2].tid,
            e->helper[h].first_ns, e->helper[h].last_ns, e->helper[h].calls, e->helper[h].waits,
            e->helper[h].wakes, e->helper[h].errors, e->helper[h].interrupted, e->helper[h].checksum);
        fprintf(f, "]}\n");
    }
    fprintf(f, "{\"type\":\"termination\",\"interrupted\":%s,\"monotonic_ns\":%"PRIu64"}\n", interrupted ? "true" : "false", aet_now());
    fclose(f);
    snprintf(name, sizeof(name), "%s/histograms.json", output); f = fopen(name, "wx"); if (!f) die("histograms.json");
    fprintf(f, "{\"sample_every\":%u,\"method\":\"log2-nanoseconds\",\"workers\":[", sample_every);
    for (unsigned w=0; w<2; w++) {
        fprintf(f, "%s{\"samples\":%"PRIu64",\"bins\":[",w ? ",":"", workers[w].hist_n);
        for (unsigned b=0; b<64; b++) fprintf(f,"%s%"PRIu64,b ? ",":"",workers[w].histogram[b]);
        fprintf(f,"]}");
    }
    fprintf(f,"]}\n"); fclose(f);
}
int main(int argc, char **argv) {
    if (argc == 2 && !strcmp(argv[1], "--selftest")) {
        uint64_t a = compute(42, 2), b = compute(42, 2);
        if (a != b || a == compute(43, 2)) return 1;
        printf("{\"checksum\":%"PRIu64",\"deterministic\":true}\n", a); return 0;
    }
    if (argc != 18) {
        fprintf(stderr,"usage: workload cpu|io output schedule.tsv tmpfs repeats seed warmup measure drift drift_at high_bg C0 C1 C2 C3 sample_every truth_aggregation\n"); return 2;
    }
    io_mode = !strcmp(argv[1], "io"); repeats = strtoul(argv[5],0,10); seed = strtoull(argv[6],0,10);
    warmup_s=atoi(argv[7]); duration_s=atoi(argv[8]); drift=atoi(argv[9]); drift_at_s=atoi(argv[10]);
    high_background=atoi(argv[11]); for(unsigned i=0;i<4;i++) cpus[i]=atoi(argv[12+i]); sample_every=atoi(argv[16]);
    truth_aggregation=atoi(argv[17]);
    if (!repeats || !duration_s || duration_s > 7200) return 2;
    pid_t parent=getppid();if(parent==1)return 2;
    if(prctl(PR_SET_PDEATHSIG,SIGTERM)||getppid()!=parent)return 2;
    struct sigaction handler={.sa_handler=signal_stop};sigemptyset(&handler.sa_mask);
    if(sigaction(SIGINT,&handler,NULL)||sigaction(SIGTERM,&handler,NULL))return 2;
    pin(cpus[0]);
    FILE *schedule = fopen(argv[3], "r"); if (!schedule) die("schedule");
    while (n_episodes < MAX_EPISODES) {
        struct episode *e=&episodes[n_episodes];
        if (fscanf(schedule,"%u %"SCNu64" %u %u",&e->id,&e->offset_ns,&e->duration_ms,&e->kind)!=4) break;
        if (e->kind > 1) return 2;
        n_episodes++;
    }
    fclose(schedule);
    for (unsigned i=0;i<6;i++) {
        workers[i].role=i; workers[i].cpu = (i==1 || i==5) ? cpus[2] : cpus[1];
        if (i<2) { workers[i].samples=calloc(SAMPLE_CAP,sizeof(struct sample)); if (!workers[i].samples) die("samples"); if(io_mode) prepare_file(&workers[i],argv[4]); }
        void *(*fn)(void *) = i<2 ? benchmark : i<4 ? incident_helper : i==4 ? contention : background;
        int rc=pthread_create(&workers[i].thread,0,fn,&workers[i]); if(rc){errno=rc;die("pthread_create");}
    }
    while(atomic_load(&ready)!=6 && !interrupted) { struct timespec t={.tv_nsec=1000000}; nanosleep(&t,0); }
    printf("{\"type\":\"ready\",\"targets\":[");
    for(unsigned i=0;i<5;i++) printf("%s{\"role\":\"%s\",\"tid\":%d}",i?",":"",(const char*[]){"worker0","worker1","futex0","futex1","contention"}[i],workers[i].tid);
    printf("],\"background_tid\":%d}\n",workers[5].tid); fflush(stdout);
    char line[128];
    if(!fgets(line,sizeof(line),stdin) || sscanf(line,"START %"SCNu64,&epoch_ns)!=1) interrupted=1;
    stop_ns=epoch_ns+(uint64_t)duration_s*1000000000ULL;
    pthread_mutex_lock(&mutex); atomic_store(&launched,1); pthread_cond_broadcast(&condition); pthread_mutex_unlock(&mutex);
    for(unsigned i=0;i<n_episodes && !interrupted;i++) {
        struct episode *e=&episodes[i]; uint64_t intended=epoch_ns+e->offset_ns;
        if (i && episodes[i-1].end_ns >= intended) { interrupted=1; break; }
        sleep_interruptible(intended); if(interrupted) break;
        atomic_store(&episode_stop,0); atomic_store(&episode_done,0); atomic_store(&turn,0);
        pthread_mutex_lock(&mutex); e->barrier_ns=aet_now(); atomic_store(&current_episode,i); pthread_cond_broadcast(&condition); pthread_mutex_unlock(&mutex);
        sleep_interruptible(e->barrier_ns+(uint64_t)e->duration_ms*1000000ULL);
        atomic_store(&episode_stop,1); syscall(SYS_futex,&turn,FUTEX_WAKE_PRIVATE,2,0,0,0);
        uint64_t deadline=aet_now()+1000000000ULL;
        while(atomic_load(&episode_done)!=(e->kind ? 1:2) && aet_now()<deadline && !interrupted) {
            struct timespec t={.tv_nsec=1000000}; nanosleep(&t,0);
        }
        e->end_ns=aet_now(); if(atomic_load(&episode_done)!=(e->kind?1:2)) interrupted=1;
    }
    if(!interrupted) sleep_interruptible(stop_ns);
    printf("{\"type\":\"parked\",\"monotonic_ns\":%"PRIu64"}\n",aet_now()); fflush(stdout);
    /* Runner detaches agent before releasing stable worker membership. */
    if(!interrupted && !fgets(line,sizeof(line),stdin)) interrupted=1;
    pthread_mutex_lock(&mutex); atomic_store(&terminating,1); atomic_store(&episode_stop,1); pthread_cond_broadcast(&condition); pthread_mutex_unlock(&mutex);
    syscall(SYS_futex,&turn,FUTEX_WAKE_PRIVATE,2,0,0,0);
    for(unsigned i=0;i<6;i++) pthread_join(workers[i].thread,0);
    save(argv[2],stop_ns);
    for(unsigned i=0;i<2;i++) { if(io_mode)close(workers[i].fd); free(workers[i].samples); }
    return interrupted ? 130 : 0;
}
