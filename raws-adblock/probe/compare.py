#!/usr/bin/env python3
"""Check three real browser captures for this synthetic suite, not web-wide parity."""
import argparse, json, sys
from pathlib import Path

OFF={'cleanThird':'executed','blockThird':'executed','exception':'executed','sameParty':'executed','redirect':'executed','cosmetic':'visible','cosmeticException':'visible','scriptlet':'absent'}
ON=dict(OFF,blockThird='failed',redirect='substituted',cosmetic='hidden',scriptlet='applied')

OFF2 = dict(OFF, lateScoped='visible', lateGeneric='visible',
            lateException='visible', procedural='visible',
            proceduralControl='visible', ordinaryControl='visible')
ON2 = dict(ON, lateScoped='hidden', lateGeneric='hidden',
           lateException='visible', procedural='hidden',
           proceduralControl='visible', ordinaryControl='visible')
EXPECTED = {'raws-native-probe/1': (OFF, ON), 'raws-native-probe/2': (OFF2, ON2)}

def outcome(report):
    if not isinstance(report, dict) or report.get('suite') not in EXPECTED:
        raise ValueError('wrong or missing fixture version')
    suite = report['suite']
    r = report.get('outcomes')
    if not isinstance(r, dict) or r.keys() != EXPECTED[suite][0].keys():
        raise ValueError('missing or unexpected test cases')
    return r

def check(control, brave, sandium):
    reports = (control, brave, sandium)
    outcomes = tuple(outcome(report) for report in reports)
    if len({report['suite'] for report in reports}) != 1:
        raise ValueError('captures must use the same fixture version')
    off, on = EXPECTED[control['suite']]
    errors = []
    for name, result, expected in zip(
            ('unblocked control', 'Brave Standard with fixture rules', 'Sandium with fixture rules'),
            outcomes, (off, on, on)):
        for key, value in expected.items():
            if result[key] != value:
                errors.append(f'{name}: {key}: expected {value!r}, got {result[key]!r}')
    return errors

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('control','brave','sandium'):p.add_argument(name,type=Path)
    a=p.parse_args()
    try: errors=check(*(json.loads(path.read_text()) for path in (a.control,a.brave,a.sandium)))
    except (OSError,ValueError) as e:sys.exit(str(e))
    if errors:sys.exit('\n'.join(errors))
    print('PASS: controlled outcomes only. Inspect request logs; no production parity claim.')
