"""Conservative budget until measured checkpoint/save timings justify tuning."""
import json
from pathlib import Path
import sys
import time


def build_seconds(start, now):
    # Match capture's maximum 15-minute allowance, native save/head 10 minutes,
    # and timeout's additional 60-second graceful termination window.
    remaining = int(start + 3300 - now - 900 - 600 - 60)
    if remaining < 60:
        raise ValueError("Insufficient remaining job time for build plus checkpoint/save reserves")
    return min(1200, remaining)


if __name__ == '__main__':
    start = json.loads((Path(sys.argv[1]) / '.checkpoint-state/job-start.json').read_text())['epoch']
    now = time.time()
    selected_path = Path(sys.argv[1]) / '.checkpoint-state/selected.json'
    plan = json.loads(selected_path.read_text())['payload']['plan'] if selected_path.exists() else {}
    layers = plan.get('layers', [])
    rollup = len(layers) >= 7 or any(x['expires_at'] < now + 2*86400 for x in layers)
    base_refresh = bool(plan.get('base')) and plan['base']['expires_at'] < now + 2*86400
    # stderr keeps stdout numeric for bounded-build.sh's command substitution.
    print('FLOW_BUILD_BUDGET', json.dumps(dict(elapsed_seconds=int(now-start),
        job_allowance=3300, capture_reserve=900, native_save_reserve=600,
        shutdown_reserve=60, minimum_build_seconds=60, layers=len(layers),
        rollup_due=rollup, base_refresh_due=base_refresh)), file=sys.stderr)
    print(build_seconds(start, now))
