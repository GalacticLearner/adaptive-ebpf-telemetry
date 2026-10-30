#ifndef AET_SINK_H
#define AET_SINK_H
#include <pthread.h>
#include <stdint.h>
#include "../common/wire.h"
struct aet_received { struct aet_event event; uint64_t receipt_ns; };
_Static_assert(sizeof(struct aet_received) == 72, "transport stride");
struct aet_sink {
    struct aet_received *queue;
    size_t capacity, head, tail, count;
    uint64_t consumed, dropped, written, bytes, limit, flush_ns;
    int fd, error, stopping;
    pthread_mutex_t mutex;
    pthread_cond_t condition;
    pthread_t thread;
};
int aet_sink_open(struct aet_sink *, const char *, uint64_t, uint64_t);
int aet_sink_push(struct aet_sink *, const struct aet_event *, uint64_t);
int aet_sink_close(struct aet_sink *);
#endif
