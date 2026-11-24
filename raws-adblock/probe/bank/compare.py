#!/usr/bin/env python3
"""Compare real neutral captures by case; never infer event causality or score parity."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from serve import TOKEN, NEXT, TRACK

P = {
    'allowed-direct': 'loaded','blocked-hop':'loaded','allowed-hop':'loaded',
    'excepted-hop':'loaded','bank-static':'visible','bank-static-allowed':'visible',
    'bank-editorial':'visible','bank-late':'visible','bank-late-allowed':'visible',
    'interaction':'intact',
}
S = {'reviewed':'retained','excepted':'retained','handler':'intact','interaction':'intact'}
EXPECT = {'passive':(P,dict(P,**{'blocked-hop':'error','bank-static':'hidden','bank-late':'hidden'})),
          'scriptlet':(S,dict(S,reviewed='removed'))}
LABELS = ('brave-off','brave-on','raws-off','raws-on')
HEX = re.compile('[0-9a-f]{64}')
SHA = re.compile('[0-9a-f]{40}')
ROOT = Path(__file__).resolve().parent

def digest(data):
    return hashlib.sha256(data).hexdigest()

def value_hash(s, pattern=HEX):
    return isinstance(s,str) and pattern.fullmatch(s) and set(s)!={'0'}

def capture(page, lane):
    if (not isinstance(page,dict) or page.keys()!={'suite','lane','run','origin','outcomes'} or
            page['suite']!='raws-neutral-bank/1' or page['lane']!=lane or
            not isinstance(page['run'],str) or not TOKEN.fullmatch(page['run']) or
            not isinstance(page['outcomes'],dict) or page['outcomes'].keys()!=EXPECT[lane][0].keys()):
        raise ValueError('Invalid, incomplete or mismatched page report')
    try:
        origin=urlsplit(page['origin'])
        if (origin.hostname!='raws-news.test' or origin.scheme not in ('http','https')
                or origin.path or origin.query or origin.fragment or
                origin.username or origin.password or
                (lane=='scriptlet' and (origin.scheme!='https' or origin.port not in (None,443)))):
            raise ValueError()
    except (TypeError,ValueError) as exc:
        raise ValueError('Invalid neutral origin') from exc
    return page

def qualification(path, lane, reports, rows, *, brave_source, raws_source):
    # Capture actual test context in a sidecar; a reviewer still audits original
    # signer/admission/network evidence. No declaration turns a model into Android.
    meta=json.loads(path.read_bytes())
    if set(meta)!={'schema','inventory','runs'} or meta['schema']!='raws-neutral-evidence/1':
        raise ValueError('Invalid bank evidence schema')
    if not all(value_hash(x,SHA) for x in (brave_source,raws_source)):
        raise ValueError('Provide exact expected Brave and RawS source commits')
    inventory=meta['inventory']
    if (not isinstance(inventory,dict) or len(inventory)!=30 or
            not all(isinstance(k,str) and k and value_hash(v) for k,v in inventory.items())):
        raise ValueError('Record same 30 effective list IDs and byte digests')
    if set(meta['runs'])!=set(LABELS):
        raise ValueError('Record all four run contexts')
    if set(rows)!=set(LABELS):
        raise ValueError('Capture/log evidence requires all contexts')
    keys={'platform','apk','package','source','phase','policy','provider','trust',
          'contents','inventory','report','parser','native','transport','activation'}
    wanted=digest((ROOT/('passive.txt' if lane=='passive' else 'reviewed-scriptlets.txt')).read_bytes())
    inv=digest(json.dumps(inventory,separators=(',',':'),sort_keys=True).encode())
    for label in LABELS:
        row=meta['runs'][label]
        enabled=label.endswith('-on')
        family=label.split('-')[0]
        if set(row)!=keys or row['platform']!='android-arm64' or row['inventory']!=inv:
            raise ValueError(label+': invalid platform or input inventory')
        if row['report']!=digest(reports[label]) or row['transport']!=digest(rows[label]):
            raise ValueError(label+': report or transport log was not recorded')
        if not value_hash(row['apk']) or not value_hash(row['source'],SHA) or not value_hash(row['native']):
            raise ValueError(label+': missing APK, source or original native evidence digest')
        if family=='raws' and (row['package'],row['source'])!=('io.github.sandeepbimt.raws',raws_source):
            raise ValueError('Use exact test RawS Android package')
        if family=='brave' and (row['package'],row['source'])!=('com.brave.browser',brave_source):
            raise ValueError('Use exact reference Brave Android package')
        if (row['phase'] not in ('cold','warm') or
                (enabled and (row['policy']!='standard' or row['contents']!=wanted or not value_hash(row['parser']))) or
                (not enabled and (row['policy'],row['provider'],row['trust'],row['contents'],row['parser'],row['activation'])!=
                 ('off','none','none',None,None,'off'))):
            raise ValueError(label+': unmatched capture policy')
        if enabled and (row['provider'],row['trust'],row['activation'])!=(
                ('additional-url','zero-privilege','none') if lane=='passive' else
                ('instrumented-slot0','zero-privilege-reviewed','explicit-lab-only')):
            raise ValueError(label+': wrong effective provider or feature activation')
    rs=meta['runs']
    for key in ('phase',):
        if len({row[key] for row in rs.values()})!=1:
            raise ValueError('Do not mix cold and warm captures')
    for family in ('brave','raws'):
        if any(rs[family+'-off'][key]!=rs[family+'-on'][key] for key in ('package','source','apk')):
            raise ValueError(family+': off and on must use the same build')
    if rs['brave-on']['apk']==rs['raws-on']['apk']:
        raise ValueError('Different browsers must have distinct APKs')

def compare(lane, reports, logs):
    pages={k:capture(json.loads(v),lane) for k,v in reports.items()}
    if len({p['run'] for p in pages.values()})!=len(pages) or len({p['origin'] for p in pages.values()})!=1:
        raise ValueError('Require distinct run IDs on the same origin')
    output={}
    for label,page in pages.items():
        enabled=label.endswith('-on')
        observed=page['outcomes']
        expected=EXPECT[lane][enabled]
        rs=Counter()
        for line in logs[label].splitlines():
            event=json.loads(line)
            if set(event)!={'route','status','run'} or event['route'] not in TRACK or (
                    event['status']!=(302 if event['route'] in NEXT else 200)):
                raise ValueError('Unexpected server event shape or status')
            if event['run']==page['run']:
                rs[event['route']]+=1
        wanted={'allowed-direct':1,**dict.fromkeys(NEXT,1),
                'allowed-target':1,'excepted-target':1,'blocked-target':int(not enabled)}
        expected_events=wanted if lane=='passive' else {}
        cases={key: {'observed':actual,'expected':expected[key],
                     'state':'expected' if actual==expected[key] else
                             'invalid-transport' if actual=='timeout' else 'different'}
               for key,actual in sorted(observed.items())}
        if lane=='passive':
            for route,n in expected_events.items():
                cases['server:'+route]={'observed':rs[route],'expected':n,
                                        'state':'expected' if rs[route]==n else 'different'}
            if any(rs[k]!=1 for k in ('allowed-direct','blocked-hop','allowed-hop','allowed-target',
                                       'excepted-hop','excepted-target')):
                cases['blocked-hop']['state']='invalid-transport-control'
        elif rs:
            raise ValueError('Scriptlet lane unexpectedly requested an image endpoint')
        output[label]=cases
    return output

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('lane',choices=EXPECT)
    p.add_argument('captures',type=Path,help='Directory containing <label>.json and <label>.jsonl')
    p.add_argument('--evidence',type=Path,help='Run metadata; without it results are unqualified')
    p.add_argument('--brave-source',help='Expected exact Brave source commit')
    p.add_argument('--raws-source',help='Expected exact RawS source commit')
    a=p.parse_args()
    def read(ext):
        return {label:(a.captures/(label+ext)).read_bytes() for label in LABELS}
    try:
        reports,logs=read('.json'),read('.jsonl')
        cases=compare(a.lane,reports,logs)
        if a.evidence:
            qualification(a.evidence,a.lane,reports,logs,
                          brave_source=a.brave_source,raws_source=a.raws_source)
        elif a.brave_source or a.raws_source:
            raise ValueError('Source pins are meaningful only with evidence')
    except (OSError,ValueError,TypeError,KeyError) as e:
        p.exit(2,f'INVALID: {e}\n')
    print(json.dumps({'status': 'matched laboratory context claimed; inspect retained evidence'
                       if a.evidence else 'unqualified' , 'cases':cases},indent=2))

if __name__=='__main__':
    main()
