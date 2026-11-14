PYTHON ?= python3
CC ?= cc
CLANG ?= clang
BPFTOOL ?= bpftool
PKG_CONFIG ?= pkg-config
BUILD := build
CFLAGS := -O2 -g -std=gnu11 -Wall -Wextra -Werror -Wno-misleading-indentation -pthread
LIBBPF_CFLAGS := $(shell $(PKG_CONFIG) --cflags libbpf)
LIBBPF_LIBS := $(shell $(PKG_CONFIG) --static --libs libbpf)

.PHONY: all build doctor test test-privileged clean calibrate pilot freeze estimate-matrix run validate analyze report status cleanup package
all: build
build: $(BUILD)/agent $(BUILD)/workload $(BUILD)/known_count $(BUILD)/policy_replay $(BUILD)/cost_check
$(BUILD):
	mkdir -p $(BUILD)
$(BUILD)/vmlinux.h: | $(BUILD)
	$(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > $@.tmp
	mv $@.tmp $@
$(BUILD)/%.bpf.o: src/bpf/%.bpf.c src/common/wire.h $(BUILD)/vmlinux.h
	$(CLANG) -g -O2 -target bpf -mcpu=v3 -D__TARGET_ARCH_x86 -I$(BUILD) -I/usr/include/$(shell $(CC) -dumpmachine) $(LIBBPF_CFLAGS) -Wall -Werror -Wno-missing-declarations -c $< -o $@
$(BUILD)/%.skel.h: $(BUILD)/%.bpf.o
	$(BPFTOOL) gen skeleton $< > $@.tmp
	mv $@.tmp $@
$(BUILD)/agent: src/agent/main.c src/agent/sink.c src/agent/sink.h src/common/wire.h src/common/policy.h src/common/cost.h src/common/timeutil.h src/common/policy.c src/common/cost.c $(BUILD)/sentinel.skel.h $(BUILD)/detail.skel.h
	$(CC) $(CFLAGS) -I$(BUILD) $(LIBBPF_CFLAGS) src/agent/main.c src/agent/sink.c src/common/policy.c src/common/cost.c $(LIBBPF_LIBS) -lm -o $@
$(BUILD)/workload: src/workloads/workload.c src/common/timeutil.h | $(BUILD)
	$(CC) $(CFLAGS) $< -o $@
$(BUILD)/known_count: src/workloads/known_count.c src/common/timeutil.h | $(BUILD)
	$(CC) $(CFLAGS) $< -o $@
$(BUILD)/policy_replay: src/common/policy.c tests/policy_replay.c | $(BUILD)
	$(CC) $(CFLAGS) $^ -lm -o $@
$(BUILD)/cost_check: src/common/cost.c tests/cost_check.c | $(BUILD)
	$(CC) $(CFLAGS) $^ -lm -o $@
doctor:
	$(PYTHON) -m runner doctor
test:
	$(PYTHON) -m runner test --unprivileged
test-privileged:
	$(PYTHON) -m runner test --privileged
calibrate pilot freeze estimate-matrix run validate analyze report status cleanup package:
	$(PYTHON) -m runner $@ $(ARGS)
clean:
	$(PYTHON) -c "from pathlib import Path; import shutil; p=Path('build').resolve(); assert p.parent==Path.cwd().resolve(); shutil.rmtree(p) if p.exists() else None"
