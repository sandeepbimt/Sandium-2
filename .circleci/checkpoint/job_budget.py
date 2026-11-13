"""Conservative budget until measured checkpoint/save timings justify tuning."""
import json
from pathlib import Path
import sys
import time


def build_seconds(start, now):
    # Match capture's maximum 30-minute allowance, native save/head 10 minutes,
    # and timeout's additional 60-second graceful termination window.
    remaining = int(start + 3300 - now - 1800 - 600 - 60)
    if remaining < 60:
        raise ValueError("Insufficient remaining job time for build plus checkpoint/save reserves")
    return min(1200, remaining)


if __name__ == '__main__':
    start = json.loads((Path(sys.argv[1]) / '.checkpoint-state/job-start.json').read_text())['epoch']
    print(build_seconds(start, time.time()))
