#!/usr/bin/env python3
"""Check effective pinned Skia-owner GN target; never mutate generated flags."""
import json
import sys

def values(payload, field):
    if isinstance(payload, dict) and field in payload:
        result = payload[field]
    elif isinstance(payload, dict) and len(payload) == 1:
        result = next(iter(payload.values())).get(field)
    else:
        raise ValueError('unexpected GN JSON shape')
    if not isinstance(result, list) or not all(isinstance(x, str) for x in result):
        raise ValueError('invalid GN property '+field)
    return result

def check(defines, cflags):
    if 'NDEBUG' not in defines:
        raise ValueError('Skia owner is missing NDEBUG')
    if any(x == 'DCHECK_ALWAYS_ON' or x.startswith('DCHECK_ALWAYS_ON=') for x in defines):
        raise ValueError('Skia owner still enables DCHECK_ALWAYS_ON')
    if '-flto=thin' not in cflags:
        raise ValueError('Skia owner is missing official ThinLTO flag')

if __name__ == '__main__':
    try:
        with open(sys.argv[1]) as f: defines=values(json.load(f), 'defines')
        with open(sys.argv[2]) as f: cflags=values(json.load(f), 'cflags')
        check(defines,cflags)
    except (ValueError, OSError, AttributeError, IndexError) as exc:
        raise SystemExit('OFFICIAL_VIZ_GN_GATE=FAIL '+str(exc))
    print('OFFICIAL_VIZ_GN_GATE=PASS target=//components/viz/service:service NDEBUG=1 DCHECK_ALWAYS_ON=absent ThinLTO=1')
