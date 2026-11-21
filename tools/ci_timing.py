"""Small monotonic phase timings for Python steps outside run_logged."""
from contextlib import contextmanager
import time


@contextmanager
def prep_phase(name):
    started = time.monotonic()
    status = 'failed'
    print(f'RAWS_PREP_START phase={name}', flush=True)
    try:
        yield
        status = 'ok'
    finally:
        elapsed = time.monotonic() - started
        print(f'RAWS_PREP_END phase={name} status={status} elapsed_seconds={elapsed:.3f}',
              flush=True)
