"""Streaming checked parser. Synthetic writers use the identical transport ABI."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import gzip
import struct
import zlib

EVENT = struct.Struct("<HHIQQIIIIIIqII")
ENVELOPE = struct.Struct("<8sIIIIQ")
BLOCK = struct.Struct("<IIQ")
RECEIPT = struct.Struct("<Q")
assert EVENT.size == 64 and ENVELOPE.size == 32 and BLOCK.size == 16


@dataclass(frozen=True)
class Event:
    version: int
    flags: int
    generation: int
    entry_ns: int
    exit_ns: int
    tgid: int
    tid: int
    syscall_id: int
    entry_cpu: int
    exit_cpu: int
    sequence: int
    result: int
    attachment_epoch: int
    reserved: int = 0


def records(path):
    path = Path(path)
    with (gzip.open(path, "rb") if path.suffix == ".gz" else path.open("rb")) as stream:
        header = stream.read(ENVELOPE.size)
        if len(header) != ENVELOPE.size or ENVELOPE.unpack(header) != (b"AETBIN1\0", 1, 0x01020304, 64, 72, 0):
            raise ValueError("unsupported or truncated detail envelope")
        while head := stream.read(BLOCK.size):
            if len(head) != BLOCK.size:
                raise ValueError("truncated block header")
            n, crc, size = BLOCK.unpack(head)
            if not 0 < n <= 1024 or size != 72 * n:
                raise ValueError("invalid block length")
            body = stream.read(size)
            if len(body) != size or zlib.crc32(body) != crc:
                raise ValueError("truncated or corrupt detail block")
            for offset in range(0, size, 72):
                event = Event(*EVENT.unpack_from(body, offset))
                receipt, = RECEIPT.unpack_from(body, offset + 64)
                if event.version != 1 or event.reserved or event.exit_ns < event.entry_ns or receipt < event.exit_ns:
                    raise ValueError("invalid record schema or clock ordering")
                if event.flags & ~1:
                    raise ValueError("unknown event flags")
                yield event, receipt


def write_records(path, values):
    with Path(path).open("xb") as stream:
        stream.write(ENVELOPE.pack(b"AETBIN1\0", 1, 0x01020304, 64, 72, 0))
        batch = []
        def flush():
            body = b"".join(batch)
            stream.write(BLOCK.pack(len(batch), zlib.crc32(body), len(body)))
            stream.write(body)
            batch.clear()
        for event, receipt in values:
            batch.append(EVENT.pack(*asdict(event).values()) + RECEIPT.pack(receipt))
            if len(batch) == 1024:
                flush()
        if batch:
            flush()
