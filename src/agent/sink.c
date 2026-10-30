#define _GNU_SOURCE
#include "sink.h"
#include "../common/timeutil.h"
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>

struct envelope { char magic[8]; uint32_t version, endian, event_bytes, stride; uint64_t reserved; };
struct block { uint32_t count, crc; uint64_t body_bytes; };
_Static_assert(sizeof(struct envelope)==32, "envelope ABI");
_Static_assert(sizeof(struct block)==16, "block ABI");
static uint32_t crc32(const void *data, size_t n) {
    const unsigned char *p=data; uint32_t crc=~0U;
    for(size_t i=0;i<n;i++) { crc^=p[i]; for(int b=0;b<8;b++)crc=(crc>>1)^((0U-(crc&1))&0xedb88320U); }
    return ~crc;
}
static int append(struct aet_sink *s, const void *data, size_t size) {
    if(s->bytes+size>s->limit) { errno=ENOSPC;return -1; }
    size_t done=0;
    while(done<size) {
        ssize_t got=pwrite(s->fd,(const char*)data+done,size-done,s->bytes+done);
        if(got<0&&errno==EINTR)continue;
        if(got<=0)return -1;
        done+=got;
    }
    s->bytes+=size;return 0;
}
static void *writer(void *arg) {
    struct aet_sink *s=arg; struct aet_received batch[1024];
    for(;;) {
        pthread_mutex_lock(&s->mutex);
        while(!s->count&&!s->stopping)pthread_cond_wait(&s->condition,&s->mutex);
        if(!s->count&&s->stopping){pthread_mutex_unlock(&s->mutex);break;}
        size_t n=s->count<1024?s->count:1024;
        for(size_t i=0;i<n;i++){batch[i]=s->queue[s->tail];s->tail=(s->tail+1)%s->capacity;}
        s->count-=n; pthread_mutex_unlock(&s->mutex);
        struct block h={.count=n,.crc=crc32(batch,n*sizeof(*batch)),.body_bytes=n*sizeof(*batch)};
        uint64_t start=aet_now();
        if(append(s,&h,sizeof(h))||append(s,batch,n*sizeof(*batch))) {
            pthread_mutex_lock(&s->mutex);s->error=errno?errno:EIO;s->dropped+=n;pthread_mutex_unlock(&s->mutex);break;
        }
        s->written+=n;s->flush_ns+=aet_now()-start;
    }
    return 0;
}
int aet_sink_open(struct aet_sink *s,const char *path,uint64_t queue_bytes,uint64_t limit) {
    memset(s,0,sizeof(*s));s->fd=-1;s->limit=limit;s->capacity=queue_bytes/sizeof(struct aet_received);
    if(!s->capacity||limit<32)return -1;
    s->queue=calloc(s->capacity,sizeof(*s->queue));if(!s->queue)return -1;
    s->fd=open(path,O_CREAT|O_EXCL|O_RDWR|O_CLOEXEC,0600);if(s->fd<0){free(s->queue);return -1;}
    int rc=posix_fallocate(s->fd,0,limit);
    if(rc){errno=rc;goto fail;}
    struct envelope header={.magic="AETBIN1",.version=1,.endian=0x01020304,.event_bytes=64,.stride=72};
    if(append(s,&header,sizeof(header)))goto fail;
    pthread_mutex_init(&s->mutex,0);pthread_cond_init(&s->condition,0);
    rc=pthread_create(&s->thread,0,writer,s);if(rc){errno=rc;goto fail;}
    return 0;
fail: close(s->fd);s->fd=-1;free(s->queue);return -1;
}
int aet_sink_push(struct aet_sink *s,const struct aet_event *event,uint64_t receipt) {
    pthread_mutex_lock(&s->mutex);s->consumed++;
    int rc=0;
    if(s->count==s->capacity||s->error){s->dropped++;rc=1;}
    else { s->queue[s->head]=(struct aet_received){.event=*event,.receipt_ns=receipt};
        s->head=(s->head+1)%s->capacity;s->count++;pthread_cond_signal(&s->condition); }
    pthread_mutex_unlock(&s->mutex);return rc;
}
int aet_sink_close(struct aet_sink *s) {
    pthread_mutex_lock(&s->mutex);s->stopping=1;pthread_cond_signal(&s->condition);pthread_mutex_unlock(&s->mutex);
    pthread_join(s->thread,0);
    s->dropped+=s->count;s->count=0;
    if(ftruncate(s->fd,s->bytes)&&!s->error)s->error=errno;
    close(s->fd);free(s->queue);pthread_mutex_destroy(&s->mutex);pthread_cond_destroy(&s->condition);
    return s->error?-1:0;
}
