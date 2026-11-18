"""Measured work counters and independent fail-closed deadline watchdog.

Output records completed work, not a liveness heartbeat. No progress for the
stall interval terminates the process, even when its I/O call is blocked.
"""
import json
import os
import threading
import time

_lock = threading.Lock()
_state = {"phase": "starting", "bytes": 0, "items": 0}
_last_work = time.monotonic()
_last_log = 0.0


def advance(bytes_done=0, items=0, phase=None):
    global _last_work, _last_log
    now = time.monotonic()
    with _lock:
        changed = phase is not None and phase != _state["phase"]
        if phase is not None:
            _state["phase"] = phase
        _state["bytes"] += bytes_done
        _state["items"] += items
        if bytes_done or items or changed:
            _last_work = now
        if changed or now - _last_log >= float(os.environ.get("FLOW_PROGRESS_INTERVAL_SECONDS", "30")):
            print("FLOW_PROGRESS " + json.dumps(_state), flush=True)
            _last_log = now


class Watchdog:
    def __init__(self, seconds, stall_seconds=300, poll_seconds=1):
        self.seconds = seconds
        self.stall = stall_seconds
        self.poll = poll_seconds
        self.stop = threading.Event()

    def __enter__(self):
        self.deadline = time.monotonic() + self.seconds
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        return self

    def run(self):
        while not self.stop.wait(self.poll):
            now = time.monotonic()
            with _lock:
                idle = now - _last_work
                snapshot = dict(_state)
            reason = "deadline" if now >= self.deadline else "no-measured-progress" if idle >= self.stall else None
            if reason:
                print("FLOW_ABORT " + json.dumps(dict(snapshot, reason=reason, idle_seconds=round(idle, 2))), flush=True)
                os._exit(124)  # No receipt/head publication after an interrupted operation.

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join()
