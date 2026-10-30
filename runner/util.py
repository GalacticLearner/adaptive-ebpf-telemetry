from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def seed_for(namespace, *parts):
    return int.from_bytes(hashlib.sha256(json.dumps([namespace, *parts], separators=(",", ":")).encode()).digest()[:8], "big")


def write_json(path, obj, *, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if exclusive:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    else:
        fd, temp = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def command(args, **kwargs):
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True, errors="replace", **kwargs)
    return {"argv": [str(x) for x in args], "returncode": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def git_state():
    head = command(["git", "rev-parse", "HEAD"], cwd=ROOT)
    dirty = command(["git", "status", "--porcelain"], cwd=ROOT)
    files = {}
    tracked = command(["git", "ls-files", "-z"], cwd=ROOT)
    for name in tracked["stdout"].split("\0"):
        if name and (ROOT / name).is_file():
            files[name] = digest(ROOT / name)
    return {"commit": head["stdout"].strip() if head["returncode"] == 0 else None,
            "dirty": bool(dirty["stdout"]), "tree_hash": canonical_hash(files)}


@contextlib.contextmanager
def host_lock(path):
    """OS-released advisory lock, including after SIGKILL; no stale PID unlink race."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        try:
            if os.name == "nt":
                import msvcrt
                stream.seek(0)
                if not stream.read(1):
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as exc:
            raise RuntimeError("another calibration/experiment owns the host lock") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)
