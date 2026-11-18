"""Bound compilation with shared plan-aware save and explicit export reserves."""
import json
import math
import re
from pathlib import Path
import sys
import time


def save_policy(plan, start):
    """Full build publishes only the new increment; maintenance has a separate job.

    Validate transport shape before allowing the ordinary save reserve.

    Unknown/seed plans retain the conservative allowance. A valid ordinary
    incremental save has neither a rollup nor a compressed-base refresh due.
    Publication remains last; this allowance is not a delivery guarantee.
    """
    conservative = dict(seconds=600, reason='unknown_plan', rollup_due=None, base_refresh_due=None)
    try:
        layers = plan['layers']; base = plan['base']
        if not isinstance(layers, list) or not layers or not isinstance(base, dict):
            return conservative
        # Receipt integrity/scope is checked by select/restore/begin before this
        # immutable plan reaches us. Require its structural chain here too;
        # incomplete records must never grant the shorter allowance.
        def ident(value):
            return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value)
        def record(value):
            return (isinstance(value, dict) and ident(value.get('id'))
                    and isinstance(value.get('key'), str) and bool(value['key'])
                    and type(value.get('expires_at')) in (int, float))
        if len(layers) > 16 or not record(base) or not ident(base.get('manifest_sha256')):
            return conservative
        expected=base['id']; seen={expected}
        for layer in layers:
            if not record(layer) or layer.get('parent') != expected or layer['id'] in seen:
                return conservative
            expected=layer['id']; seen.add(expected)
        if plan.get('head') != expected:
            return conservative
        cutoff = float(start) + 3600 + 2 * 86400
        expiries = [float(x['expires_at']) for x in layers]
        base_expiry = float(base['expires_at'])
        if not all(math.isfinite(x) for x in [cutoff, base_expiry] + expiries):
            return conservative
        rollup = len(layers) >= 7 or any(x <= cutoff for x in expiries)
        refresh = base_expiry <= cutoff
    except (KeyError, TypeError, ValueError, OverflowError):
        return conservative
    return dict(seconds=300, reason='new_increment_only',
                rollup_due=False, base_refresh_due=False)


def build_seconds(start, now, plan=None):
    # Keep full capture and termination reserves. Only an ordinary delta uses
    # five-minute save/head allowance; all uncertain plans use ten. Ordinary
    # observed save was 13 seconds; 300 seconds is a margin, not a guarantee.
    # Export/audit occurs before capture and receives its own three minutes.
    remaining = int(start + 3300 - now - 900 - save_policy(plan, start)['seconds'] - 60 - 180)
    if remaining < 60:
        raise ValueError("Insufficient remaining job time for build plus checkpoint/save reserves")
    return min(2100, remaining)


if __name__ == '__main__':
    start = json.loads((Path(sys.argv[1]) / '.checkpoint-state/job-start.json').read_text())['epoch']
    now = time.time()
    selected_path = Path(sys.argv[1]) / '.checkpoint-state/selected.json'
    try:
        plan = json.loads(selected_path.read_text())['payload']['plan']
    except (OSError, KeyError, TypeError, ValueError):
        plan = None
    policy = save_policy(plan, start)
    layers = plan.get('layers', []) if isinstance(plan,dict) else []
    if not isinstance(layers,list): layers=[]
    # stderr keeps stdout numeric for bounded-build.sh's command substitution.
    print('FULL_BUILD_BUDGET', json.dumps(dict(elapsed_seconds=int(now-start),
        job_allowance=3300, capture_reserve=900, native_save_reserve=policy['seconds'], save_policy=policy['reason'],
        shutdown_reserve=60, postbuild_reserve=180, minimum_build_seconds=60, layers=len(layers),
        rollup_due=policy['rollup_due'], base_refresh_due=policy['base_refresh_due'])), file=sys.stderr)
    print(build_seconds(start, now, plan))
