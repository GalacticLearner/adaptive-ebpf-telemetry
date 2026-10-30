// SPDX-License-Identifier: MIT
#define _GNU_SOURCE
#include <bpf/libbpf.h>
#include <bpf/bpf.h>
#include <linux/bpf.h>
#include <sys/epoll.h>
#include <sys/timerfd.h>
#include <sys/signalfd.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <sys/resource.h>
#include <unistd.h>
#include <sched.h>
#include <signal.h>
#include <errno.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <inttypes.h>
#include <stdatomic.h>
#include "sentinel.skel.h"
#include "detail.skel.h"
#include "../common/wire.h"
#include "../common/policy.h"
#include "../common/cost.h"
#include "../common/timeutil.h"
#include "sink.h"

struct runtime {
    char policy[32]; unsigned period_ms, dwell_ms, grace_ms, hysteresis, supervisor, stats, component, signal_total;
    int cpu1, cpu2, isolated;
    uint64_t ring_bytes, queue_bytes, stage_bytes;
    double median, scale, high, budget, rate_low, rate_high;
    double cost[3][3][3], fallback[3], transition[3];
};
struct agent {
    struct sentinel_bpf *sent;
    struct detail_bpf *detail;
    struct bpf_link *sent_link, *entry, *exit;
    struct ring_buffer *ring;
    struct aet_sink sink;
    struct runtime cfg;
    struct aet_policy policy;
    FILE *ticks, *transitions, *bin_log;
    uint64_t generation, attachment_epoch, last_bin, deadline, abandoned, applied_ns;
    int mechanism_switch, applied, queued, draining, failed, ncpu, polltimer;
    double utilization;
    uint64_t prev_cpu_total, prev_cpu_idle;
    struct aet_bin *bin_values, *bin_verify;
    struct aet_counters *counter_values;
};
static int read_counts(struct agent *a,struct aet_counters *total) {
    uint32_t zero=0;memset(total,0,sizeof(*total));
    if(!a->counter_values||bpf_map_lookup_elem(bpf_map__fd(a->detail->maps.counters),&zero,a->counter_values))return -1;
    for(int c=0;c<a->ncpu;c++) {
#define ADD(name) total->name+=a->counter_values[c].name
        ADD(eligible);ADD(rejected);ADD(selected);ADD(insert_failed);ADD(replaced);ADD(malformed);
        ADD(exit_without_selected);ADD(completed);ADD(reserve_failed);ADD(emitted);
#undef ADD
    }
    return 0;
}

static void failure(const char *s) { perror(s); }
static FILE *open_output(const char *dir,const char *name) {
    char path[4096];snprintf(path,sizeof(path),"%s/%s",dir,name);return fopen(path,"wx");
}
static int runtime_read(struct runtime *c,const char *path) {
    FILE *f=fopen(path,"r");if(!f)return -1;
    memset(c,0,sizeof(*c));
    for(int m=0;m<3;m++){c->transition[m]=c->fallback[m]=NAN;for(int r=0;r<3;r++)for(int u=0;u<3;u++)c->cost[m][r][u]=NAN;}
    char key[64], value[128];
    while(fscanf(f,"%63s %127s",key,value)==2) {
        if(!strcmp(key,"policy")){if(strlen(value)>=sizeof(c->policy)){fclose(f);return -1;}strcpy(c->policy,value);}
#define UINT_FIELD(name) else if(!strcmp(key,#name))c->name=strtoull(value,0,10)
#define FLOAT_FIELD(name) else if(!strcmp(key,#name))c->name=strtod(value,0)
        UINT_FIELD(period_ms);UINT_FIELD(dwell_ms);UINT_FIELD(grace_ms);UINT_FIELD(hysteresis);UINT_FIELD(supervisor);
        UINT_FIELD(stats);UINT_FIELD(component);UINT_FIELD(signal_total);UINT_FIELD(cpu1);UINT_FIELD(cpu2);UINT_FIELD(isolated);
        UINT_FIELD(ring_bytes);UINT_FIELD(queue_bytes);UINT_FIELD(stage_bytes);
        FLOAT_FIELD(median);FLOAT_FIELD(scale);FLOAT_FIELD(high);FLOAT_FIELD(budget);FLOAT_FIELD(rate_low);FLOAT_FIELD(rate_high);
        else {
            unsigned m,r,u;
            if(sscanf(key,"cost_%u_%u_%u",&m,&r,&u)==3&&m<3&&r<3&&u<3)c->cost[m][r][u]=strtod(value,0);
            else if(sscanf(key,"transition_%u",&m)==1&&m<3)c->transition[m]=strtod(value,0);
            else if(sscanf(key,"fallback_%u",&m)==1&&m<3)c->fallback[m]=strtod(value,0);
            else {fclose(f);errno=EINVAL;return -1;}
        }
#undef UINT_FIELD
#undef FLOAT_FIELD
    }
    fclose(f);
    if(!c->period_ms||c->scale<.10||!isfinite(c->median)||!isfinite(c->high)||c->high<=0||!c->stage_bytes)return -1;
    return 0;
}
static void publish(struct agent *a,int mode) {
    uint32_t q=mode==AET_HIGH?UINT32_MAX:mode==AET_MEDIUM?aet_threshold(.1):0;
    if(mode!=AET_LOW&&!strcmp(a->cfg.policy,"FIX_Q01"))q=aet_threshold(.01);
    if(mode!=AET_LOW&&!strcmp(a->cfg.policy,"FIX_Q50"))q=aet_threshold(.5);
    uint64_t word=(++a->generation<<32)|q;
    __atomic_store_n(&a->detail->bss->config_word,word,__ATOMIC_RELEASE);
}
static unsigned pending(struct agent *a) {
    unsigned count=0;uint32_t key,next;int rc=bpf_map_get_next_key(bpf_map__fd(a->detail->maps.inflight),NULL,&next);
    while(!rc){count++;key=next;rc=bpf_map_get_next_key(bpf_map__fd(a->detail->maps.inflight),&key,&next);}
    return count;
}
static void abandon(struct agent *a) {
    uint32_t key;
    int fd=bpf_map__fd(a->detail->maps.inflight);
    /* Both handlers detached before deletion. Exact final accounting requires quiescence test. */
    while(!bpf_map_get_next_key(fd,NULL,&key)) {
        if(!bpf_map_delete_elem(fd,&key))a->abandoned++;
        else {a->failed=1;break;}
    }
}
static void transition_log(struct agent *a,const char *action,uint64_t desired,uint64_t start,uint64_t ack,int mode) {
    struct bpf_link_info info={0};uint32_t size=sizeof(info);unsigned entry_id=0,exit_id=0;
    if(a->entry&&!bpf_obj_get_info_by_fd(bpf_link__fd(a->entry),&info,&size))entry_id=info.id;
    memset(&info,0,sizeof(info));size=sizeof(info);
    if(a->exit&&!bpf_obj_get_info_by_fd(bpf_link__fd(a->exit),&info,&size))exit_id=info.id;
    fprintf(a->transitions,"{\"action\":\"%s\",\"desired_ns\":%"PRIu64",\"action_start_ns\":%"PRIu64",\"ack_ns\":%"PRIu64",\"mode\":%d,\"generation\":%"PRIu64",\"attachment_epoch\":%"PRIu64",\"entry_link\":%u,\"exit_link\":%u,\"forced_abandoned\":%"PRIu64"}\n",
        action,desired,start,ack,mode,a->generation,a->attachment_epoch,entry_id,exit_id,a->abandoned);
}
static int attach(struct agent *a,int mode,uint64_t desired) {
    uint64_t start=aet_now();publish(a,AET_LOW);
    if(!a->exit) {
        uint64_t hook_start=aet_now();
        a->exit=bpf_program__attach_tracepoint(a->detail->progs.detail_exit,"raw_syscalls","sys_exit");
        if(libbpf_get_error(a->exit)){a->exit=NULL;goto fail;}
        transition_log(a,"attach_exit",desired,hook_start,aet_now(),AET_LOW);
    }
    if(!a->entry) {
        uint64_t hook_start=aet_now();
        a->entry=bpf_program__attach_tracepoint(a->detail->progs.detail_enter,"raw_syscalls","sys_enter");
        if(libbpf_get_error(a->entry)){a->entry=NULL;goto fail;}
        a->detail->bss->attachment_epoch=++a->attachment_epoch;
        transition_log(a,"attach_entry",desired,hook_start,aet_now(),AET_LOW);
    }
    publish(a,mode);a->applied=mode;a->applied_ns=aet_now();a->policy.last_change_ns=a->applied_ns;
    transition_log(a,"activate",desired,start,a->applied_ns,mode);return 0;
fail:
    publish(a,AET_LOW);bpf_link__destroy(a->entry);bpf_link__destroy(a->exit);a->entry=a->exit=NULL;
    transition_log(a,"attach_failed",desired,start,aet_now(),AET_LOW);a->failed=1;return -1;
}
static void request(struct agent *a,int mode,uint64_t now) {
    a->queued=mode;
    if(a->draining)return;
    if(mode==a->applied)return;
    uint64_t start=aet_now();
    if(mode==AET_LOW) {
        publish(a,AET_LOW);
        if(a->mechanism_switch) {
            bpf_link__destroy(a->entry);a->entry=NULL;a->draining=1;
            a->deadline=start+(uint64_t)a->cfg.grace_ms*1000000ULL;
            struct itimerspec every_ms={.it_interval={.tv_nsec=1000000},.it_value={.tv_nsec=1000000}};
            if(timerfd_settime(a->polltimer,0,&every_ms,NULL))a->failed=1;
            transition_log(a,"drain_start",now,start,aet_now(),AET_LOW);
        } else {
            a->applied=AET_LOW;a->applied_ns=aet_now();a->policy.last_change_ns=a->applied_ns;
            transition_log(a,"gate_low_cutoff",now,start,a->applied_ns,AET_LOW);
        }
    } else if(!a->entry) attach(a,mode,now);
    else {
        publish(a,mode);a->applied=mode;a->applied_ns=aet_now();a->policy.last_change_ns=a->applied_ns;
        transition_log(a,"publish",now,start,a->applied_ns,mode);
    }
}
static void poll_transition(struct agent *a,uint64_t now) {
    if(!a->draining)return;
    if(pending(a)==0||now>=a->deadline) {
        uint64_t start=aet_now();bpf_link__destroy(a->exit);a->exit=NULL;abandon(a);
        a->draining=0;a->applied=AET_LOW;a->applied_ns=aet_now();a->policy.last_change_ns=a->applied_ns;
        struct itimerspec disabled={0};if(timerfd_settime(a->polltimer,0,&disabled,NULL))a->failed=1;
        transition_log(a,"drain_complete",a->deadline-(uint64_t)a->cfg.grace_ms*1000000ULL,start,a->applied_ns,AET_LOW);
        if(a->queued!=AET_LOW)attach(a,a->queued,now);
    }
}
static int receive(void *context,void *data,size_t size) {
    struct agent *a=context;
    if(size!=sizeof(struct aet_event)){a->failed=1;return -EINVAL;}
    const struct aet_event *event=data;
    uint64_t now=aet_now();
    if(event->version!=1||event->exit_ns<event->entry_ns||now<event->exit_ns){a->failed=1;return -EINVAL;}
    aet_sink_push(&a->sink,event,now);return 0;
}
static int targets(struct agent *a,const char *path) {
    FILE *f=fopen(path,"r");if(!f)return -1;uint32_t tid,value=0;unsigned n=0;
    while(fscanf(f,"%u",&tid)==1) {
        if(++n>AET_MAX_TARGETS||bpf_map_update_elem(bpf_map__fd(a->sent->maps.targets),&tid,&value,BPF_NOEXIST)||
           bpf_map_update_elem(bpf_map__fd(a->detail->maps.targets),&tid,&value,BPF_NOEXIST)){fclose(f);return -1;}
    }
    fclose(f);return n?0:-1;
}
static void cpu_context(struct agent *a) {
    FILE *f=fopen("/proc/stat","r");if(!f){a->utilization=NAN;return;}
    char line[1024];uint64_t total=0,idle=0;
    while(fgets(line,sizeof(line),f)) {
        int cpu;unsigned long long v[10]={0};
        if(sscanf(line,"cpu%d %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu",&cpu,&v[0],&v[1],&v[2],&v[3],&v[4],&v[5],&v[6],&v[7],&v[8],&v[9])<5)continue;
        if(cpu!=a->cfg.cpu1&&cpu!=a->cfg.cpu2)continue;
        /* guest is included in user/nice; do not double-count it. */
        for(int i=0;i<8;i++)total+=v[i];idle+=v[3]+v[4];
    }
    fclose(f);
    uint64_t dt=total-a->prev_cpu_total,di=idle-a->prev_cpu_idle;
    a->utilization=a->prev_cpu_total&&dt?1.0-(double)di/dt:NAN;
    a->prev_cpu_total=total;a->prev_cpu_idle=idle;
}
static int fixed_mode(const char *p) {
    if(!strcmp(p,"FIX_MED"))return AET_MEDIUM;
    if(!strcmp(p,"FIX_HIGH")||!strcmp(p,"FIX_Q50")||!strcmp(p,"FIX_Q01")||!strcmp(p,"EMPTY")||!strcmp(p,"FILTER")||!strcmp(p,"PAIR")||!strcmp(p,"SHADOW"))return AET_HIGH;
    return AET_LOW;
}
static void tick(struct agent *a,uint64_t now) {
    struct timespec cpu_before,cpu_after;clock_gettime(CLOCK_THREAD_CPUTIME_ID,&cpu_before);
    uint64_t cutoff=(now-10000000ULL)/AET_BIN_NS;
    uint64_t current=now/AET_BIN_NS,total=0,first=a->last_bin+1,valid=0;
    bool gap=false;
    double maximum=0;
    if(cutoff>a->last_bin+AET_BINS){gap=true;a->last_bin=cutoff-AET_BINS;}
    /* cutoff names the first bin NOT fully closed before the safety boundary. */
    for(uint64_t bin=a->last_bin+1;bin<cutoff;bin++) {
        uint32_t key=bin%AET_BINS;uint64_t count=0;
        int rc=bpf_map_lookup_elem(bpf_map__fd(a->sent->maps.bins),&key,a->bin_values);
        if(!rc)rc=bpf_map_lookup_elem(bpf_map__fd(a->sent->maps.bins),&key,a->bin_verify);
        bool ok=!rc;
        for(int cpu=0;ok&&cpu<a->ncpu;cpu++) {
            uint64_t value=0;struct aet_bin b=a->bin_values[cpu];
            if(b.seq!=a->bin_verify[cpu].seq||aet_bin_read(bin,current,b.epoch,b.count,b.seq,&value))ok=false;
            else count+=value;
        }
        if(!ok)gap=true;
        else {double s=aet_score(count,a->cfg.median,a->cfg.scale);if(s>maximum)maximum=s;total+=count;valid++;}
        fprintf(a->bin_log,"%"PRIu64",%"PRIu64",%d\n",bin,count,ok?1:0);
        a->last_bin=bin;
    }
    if(a->cfg.signal_total)maximum=aet_score(total,a->cfg.median,a->cfg.scale);
    cpu_context(a);
    double rate=valid?(double)total/((double)valid*.005):NAN;
    a->policy.applied=a->applied;
    struct aet_policy preview=a->policy;
    struct aet_decision wanted=aet_tick(&preview,now,maximum,gap,AET_HIGH);
    struct aet_cost_result cost={.allowed=AET_HIGH,.prediction=NAN};
    if(a->cfg.supervisor)cost=aet_cost_choose(wanted.requested,a->applied,rate,a->utilization,a->cfg.rate_low,a->cfg.rate_high,
        a->cfg.budget,a->cfg.cost,a->cfg.fallback,a->cfg.transition);
    int allowed=cost.allowed;
    struct aet_decision d=aet_tick(&a->policy,now,maximum,gap,allowed);
    bool adaptive=!strncmp(a->cfg.policy,"ADAPT",5)||!strncmp(a->cfg.policy,"TRIGGER",7);
    if(adaptive)request(a,d.applied,now);
    clock_gettime(CLOCK_THREAD_CPUTIME_ID,&cpu_after);
    uint64_t cpu_ns=(uint64_t)(cpu_after.tv_sec-cpu_before.tv_sec)*1000000000ULL+cpu_after.tv_nsec-cpu_before.tv_nsec;
    struct aet_counters counters={0};if(read_counts(a,&counters))a->failed=1;
    pthread_mutex_lock(&a->sink.mutex);uint64_t consumed=a->sink.consumed,sink_drop=a->sink.dropped;pthread_mutex_unlock(&a->sink.mutex);
    fprintf(a->ticks,"%"PRIu64",%"PRIu64",%"PRIu64",%"PRIu64",%.9g,%d,%d,%d,%d,%d,%u,%"PRIu64",%.9g,%.9g,%.9g,%d,%d,%d,%d,%d,%d,%"PRIu64",%d,%llu,%llu,%llu,%llu,%llu,%"PRIu64",%"PRIu64",%d,%d\n",
        now,first,a->last_bin,total,maximum,gap,d.requested,allowed,a->applied,a->draining,
        (uint32_t)a->detail->bss->config_word,a->generation,cost.prediction,rate,a->utilization,d.alert,d.alert_started,
        d.dwell_deferred,d.budget_override,cost.infeasible,cost.fallback,cpu_ns,cost.transition_unresolved,
        (unsigned long long)counters.eligible,(unsigned long long)counters.selected,(unsigned long long)counters.completed,
        (unsigned long long)counters.reserve_failed,(unsigned long long)counters.emitted,consumed,sink_drop,a->entry!=NULL,a->exit!=NULL);
}
static int final_counts(struct agent *a,const char *output) {
    struct aet_counters total={0};if(read_counts(a,&total))return -1;
    unsigned left=pending(a);uint64_t undrained=total.emitted>a->sink.consumed?total.emitted-a->sink.consumed:0;
    bool ledger=total.selected==total.insert_failed+total.replaced+total.malformed+total.completed+a->abandoned+left &&
        total.eligible==total.selected+total.rejected &&
        (a->cfg.component==3||total.completed==total.emitted+total.reserve_failed) &&
        total.emitted==a->sink.consumed+undrained && a->sink.consumed==a->sink.written+a->sink.dropped;
    FILE *f=open_output(output,"counters.json");if(!f)return -1;
    fprintf(f,"{\"schema_version\":1,\"eligible\":%"PRIu64",\"selected\":%"PRIu64",\"rejected\":%"PRIu64",\"insert_failed\":%"PRIu64",\"replaced\":%"PRIu64",\"malformed\":%"PRIu64",\"exit_without_selected\":%"PRIu64",\"completed\":%"PRIu64",\"reserve_failed\":%"PRIu64",\"emitted\":%"PRIu64",\"abandoned\":%"PRIu64",\"pending\":%u,\"consumed\":%"PRIu64",\"sink_drop\":%"PRIu64",\"written\":%"PRIu64",\"undrained\":%"PRIu64",\"sink_bytes\":%"PRIu64",\"sink_flush_ns\":%"PRIu64",\"sink_error\":%d,\"ledger_ok\":%s,\"stats_enabled\":%s,\"component\":%u}\n",
        (uint64_t)total.eligible,(uint64_t)total.selected,(uint64_t)total.rejected,(uint64_t)total.insert_failed,(uint64_t)total.replaced,(uint64_t)total.malformed,(uint64_t)total.exit_without_selected,
        (uint64_t)total.completed,(uint64_t)total.reserve_failed,(uint64_t)total.emitted,a->abandoned,left,a->sink.consumed,a->sink.dropped,a->sink.written,
        undrained,a->sink.bytes,a->sink.flush_ns,a->sink.error,ledger?"true":"false",a->cfg.stats?"true":"false",a->cfg.component);
    fclose(f);return ledger?0:-1;
}
int main(int argc,char **argv) {
    if(argc!=5){fprintf(stderr,"usage: agent output targets.txt runtime.conf staging.bin\n");return 2;}
#if !defined(__x86_64__) || __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
    fprintf(stderr,"unsupported ABI: x86-64 little endian required\n");return 2;
#endif
    struct agent a={0};int result=2,stats_fd=-1,ep=-1,timer=-1,polltimer=-1,signal_fd=-1,sink_open=0;
    if(runtime_read(&a.cfg,argv[3])){failure("runtime config");return 2;}
    cpu_set_t mask;CPU_ZERO(&mask);CPU_SET(a.cfg.cpu1,&mask);CPU_SET(a.cfg.cpu2,&mask);
    if(a.cfg.isolated){CPU_ZERO(&mask);CPU_SET(a.cfg.isolated-1,&mask);}
    if(sched_setaffinity(0,sizeof(mask),&mask)){failure("agent affinity");return 2;}
    pid_t parent=getppid();if(parent==1||prctl(PR_SET_PDEATHSIG,SIGTERM)||getppid()!=parent)return 2;
    sigset_t signals;sigemptyset(&signals);sigaddset(&signals,SIGINT);sigaddset(&signals,SIGTERM);
    if(pthread_sigmask(SIG_BLOCK,&signals,0))return 2;
    a.mechanism_switch=strstr(a.cfg.policy,"SWITCH")||!strcmp(a.cfg.policy,"SENT");
    a.policy=(struct aet_policy){.high=a.cfg.high,.period_ms=a.cfg.period_ms,.dwell_ms=a.cfg.dwell_ms,.recovery_ms=500,.hysteresis=a.cfg.hysteresis};
    a.ticks=open_output(argv[1],"ticks.csv");a.transitions=open_output(argv[1],"transitions.jsonl");a.bin_log=open_output(argv[1],"bins.csv");
    if(!a.ticks||!a.transitions||!a.bin_log)goto cleanup;
    fprintf(a.ticks,"monotonic_ns,first_bin,last_bin,count,score,gap,requested,allowed,applied,draining,threshold,generation,prediction,rate,utilization,alert,alert_started,dwell_deferred,budget_override,budget_infeasible,fallback,controller_cpu_ns,transition_cost_unresolved,eligible,selected,completed,reserve_failed,emitted,consumed,sink_drop,entry_attached,exit_attached\n");
    fprintf(a.bin_log,"absolute_bin,count,valid\n");
    if(a.cfg.stats){stats_fd=bpf_enable_stats(BPF_STATS_RUN_TIME);if(stats_fd<0){failure("BPF runtime stats");goto cleanup;}}
    a.sent=sentinel_bpf__open();a.detail=detail_bpf__open();if(!a.sent||!a.detail)goto cleanup;
    a.detail->rodata->component=a.cfg.component;
    if(bpf_map__set_max_entries(a.detail->maps.events,a.cfg.ring_bytes))goto cleanup;
    if(sentinel_bpf__load(a.sent)||detail_bpf__load(a.detail)){failure("load BPF (preserve verifier stderr)");goto cleanup;}
    if(targets(&a,argv[2])){failure("targets");goto cleanup;}
    unsigned ids[]={SYS_pread64,SYS_futex,SYS_sched_yield,SYS_clock_nanosleep};uint32_t yes=1;
    for(unsigned i=0;i<4;i++)if(bpf_map_update_elem(bpf_map__fd(a.detail->maps.allowlist),&ids[i],&yes,BPF_ANY))goto cleanup;
    a.ncpu=libbpf_num_possible_cpus();if(a.ncpu<=0)goto cleanup;
    a.counter_values=calloc(a.ncpu,sizeof(*a.counter_values));if(!a.counter_values)goto cleanup;
    a.bin_values=calloc(a.ncpu,sizeof(*a.bin_values));a.bin_verify=calloc(a.ncpu,sizeof(*a.bin_verify));if(!a.bin_values||!a.bin_verify)goto cleanup;
    /* Consistent empty initialization; zero-generation is not an active modern bin. */
    for(int i=0;i<a.ncpu;i++)a.bin_values[i].epoch=AET_EMPTY_EPOCH;
    for(uint32_t i=0;i<AET_BINS;i++)if(bpf_map_update_elem(bpf_map__fd(a.sent->maps.bins),&i,a.bin_values,BPF_ANY))goto cleanup;
    if(aet_sink_open(&a.sink,argv[4],a.cfg.queue_bytes,a.cfg.stage_bytes)){failure("sink");goto cleanup;}sink_open=1;
    a.ring=ring_buffer__new(bpf_map__fd(a.detail->maps.events),receive,&a,NULL);if(!a.ring)goto cleanup;
    bool loaded_only=!strcmp(a.cfg.policy,"LOADED");
    if(!loaded_only) {
        a.sent_link=bpf_program__attach_tracepoint(a.sent->progs.sentinel_switch,"sched","sched_switch");
        if(libbpf_get_error(a.sent_link)){a.sent_link=NULL;goto cleanup;}
        if(!a.mechanism_switch&&attach(&a,fixed_mode(a.cfg.policy),aet_now()))goto cleanup;
    }
    a.last_bin=aet_now()/AET_BIN_NS;
    timer=timerfd_create(CLOCK_MONOTONIC,TFD_NONBLOCK|TFD_CLOEXEC);
    polltimer=timerfd_create(CLOCK_MONOTONIC,TFD_NONBLOCK|TFD_CLOEXEC);
    a.polltimer=polltimer;
    signal_fd=signalfd(-1,&signals,SFD_NONBLOCK|SFD_CLOEXEC);ep=epoll_create1(EPOLL_CLOEXEC);
    if(timer<0||polltimer<0||signal_fd<0||ep<0)goto cleanup;
    struct itimerspec period={.it_interval={.tv_sec=a.cfg.period_ms/1000,.tv_nsec=(a.cfg.period_ms%1000)*1000000},.it_value={.tv_nsec=1000000}};
    struct itimerspec drain={0};
    if(timerfd_settime(timer,0,&period,NULL)||timerfd_settime(polltimer,0,&drain,NULL))goto cleanup;
    int fds[]={timer,polltimer,signal_fd,ring_buffer__epoll_fd(a.ring)};
    for(int i=0;i<4;i++){struct epoll_event e={.events=EPOLLIN,.data.u32=i};if(epoll_ctl(ep,EPOLL_CTL_ADD,fds[i],&e))goto cleanup;}
    printf("{\"ready\":true,\"monotonic_ns\":%"PRIu64",\"possible_cpus\":%d,\"sentinel_bin_bytes\":%zu,\"ring_bytes\":%"PRIu64",\"queue_bytes\":%"PRIu64"}\n",aet_now(),a.ncpu,sizeof(struct aet_bin)*(size_t)a.ncpu*AET_BINS,a.cfg.ring_bytes,a.cfg.queue_bytes);fflush(stdout);
    result=0;bool running=true;
    while(running&&!a.failed) {
        struct epoll_event events[8];int n=epoll_wait(ep,events,8,-1);
        if(n<0){if(errno==EINTR)continue;result=2;break;}
        for(int i=0;i<n;i++) {
            uint64_t expirations;
            switch(events[i].data.u32) {
            case 0:if(read(timer,&expirations,8)==8&&!loaded_only)tick(&a,aet_now());break;
            case 1:if(read(polltimer,&expirations,8)==8)poll_transition(&a,aet_now());break;
            case 2:running=false;break;
            case 3:if(ring_buffer__consume(a.ring)<0)a.failed=1;break;
            }
        }
        pthread_mutex_lock(&a.sink.mutex);int sink_error=a.sink.error;pthread_mutex_unlock(&a.sink.mutex);
        if(sink_error){failure("sink write/capacity failure");a.failed=1;}
    }
cleanup:
    if(a.detail&&a.detail->bss&&a.detail->bss->config_word)publish(&a,AET_LOW);
    bpf_link__destroy(a.entry);a.entry=NULL;
    /* Runner parks target workers before SIGTERM; all selected exits have bounded grace. */
    if(a.exit&&a.ring) {
        uint64_t until=aet_now()+(uint64_t)a.cfg.grace_ms*1000000ULL;
        while(pending(&a)&&aet_now()<until){ring_buffer__poll(a.ring,1);}
    }
    bpf_link__destroy(a.exit);a.exit=NULL;bpf_link__destroy(a.sent_link);a.sent_link=NULL;
    if(a.detail&&bpf_map__fd(a.detail->maps.inflight)>=0)abandon(&a);
    if(a.ring)while(ring_buffer__consume(a.ring)>0){}
    if(sink_open) {
        if(aet_sink_close(&a.sink))result=2;
        if(final_counts(&a,argv[1]))result=2;
    }
    if(a.failed)result=2;
    ring_buffer__free(a.ring);sentinel_bpf__destroy(a.sent);detail_bpf__destroy(a.detail);
    free(a.bin_values);free(a.bin_verify);free(a.counter_values);
    if(a.ticks)fclose(a.ticks);if(a.transitions)fclose(a.transitions);if(a.bin_log)fclose(a.bin_log);
    if(stats_fd>=0)close(stats_fd);if(ep>=0)close(ep);if(timer>=0)close(timer);if(polltimer>=0)close(polltimer);if(signal_fd>=0)close(signal_fd);
    return result;
}
