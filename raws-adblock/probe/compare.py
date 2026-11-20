#!/usr/bin/env python3
"""Check three real browser captures for this synthetic suite, not web-wide parity."""
import argparse, json, sys
from pathlib import Path

OFF={'cleanThird':'executed','blockThird':'executed','exception':'executed','sameParty':'executed','redirect':'executed','cosmetic':'visible','cosmeticException':'visible','scriptlet':'absent'}
ON=dict(OFF,blockThird='failed',redirect='substituted',cosmetic='hidden',scriptlet='applied')

def outcome(report):
    if not isinstance(report,dict) or report.get('suite')!='raws-native-probe/1': raise ValueError('wrong or missing fixture version')
    r=report.get('outcomes');
    if not isinstance(r,dict) or r.keys()!=OFF.keys(): raise ValueError('missing or unexpected test cases')
    return r

def check(control,brave,sandium):
    errors=[]
    for name, report, expected in [('unblocked control',control,OFF),('Brave Standard with fixture rules',brave,ON),('Sandium with fixture rules',sandium,ON)]:
        result=outcome(report)
        for key,value in expected.items():
            if result[key]!=value: errors.append(f'{name}: {key}: expected {value!r}, got {result[key]!r}')
    return errors

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('control','brave','sandium'):p.add_argument(name,type=Path)
    a=p.parse_args()
    try: errors=check(*(json.loads(path.read_text()) for path in (a.control,a.brave,a.sandium)))
    except (OSError,ValueError) as e:sys.exit(str(e))
    if errors:sys.exit('\n'.join(errors))
    print('PASS: eight controlled outcomes only. Inspect request logs; no production parity claim.')
