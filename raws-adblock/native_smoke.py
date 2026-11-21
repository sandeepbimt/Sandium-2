#!/usr/bin/env python3
"""Run only the host Rust/CXX smoke target inside a prepared disposable RawS 158 tree.

Does not fetch, install sources, alter CI, build an APK or write to any existing
output. Use a scratch clone prepared with RawS's Siso compatibility patch, DEPS,
runhooks and remote configuration. The normal RawS baseline gates remain separate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import stage

ROOT = '//components/sandium_adblock:host_smoke'
SMOKE = '//components/sandium_adblock:engine_smoke'
ARG_BLOB = '1d4e68aaba57773bc73ea521a3db46a16233646e'
CASES = ('third-party', 'exception', 'important', 'type', 'ordinary-first-party',
         'additional-first-party', 'youtube-initiator', 'not-fake-third-party', 'lookalike')


def needed_tool(name):
    path = shutil.which(name)
    if path is None:
        raise ValueError(f'{name} not in PATH; use the RawS build-host environment')
    return path


def verify_output(text):
    expected = ['ok '+case for case in CASES] + ['RAWS_ENGINE_SMOKE_V2_PASS']
    if text.splitlines() != expected:
        raise ValueError('unexpected engine test output; no pass receipt')


def verify_port_output(text):
    expected = ['RAWS_1471_INCIDENT_RULES_PASS', 'RAWS_ENGINE_SMOKE_1442_PASS']
    if text.splitlines() != expected:
        raise ValueError('Unexpected #1442 and player incident native smoke output')


def verify_tree(expected, src):
    """Compare installed regular files (including modes) with a fresh Git-object staging."""
    receipt = json.loads((expected/'source-receipt.json').read_bytes())
    actual = {}
    for base in ('brave', 'components/sandium_adblock'):
        start = src / base
        if not start.is_dir() or start.resolve() != start:
            raise ValueError('missing or symlinked source root: '+base)
        for parent, dirs, names in os.walk(start):
            parent = Path(parent)
            for name in dirs+names:
                if (parent/name).is_symlink():
                    raise ValueError(f'symlink under installed overlay: {parent/name}')
            for name in names:
                f = parent/name
                if not f.is_file(): raise ValueError(f'non-file under installed overlay: {f}')
                key=f.relative_to(src).as_posix()
                if key not in receipt['sha256']: raise ValueError('unexpected overlay file: '+key)
                if ((f.stat().st_mode ^ (expected/key).stat().st_mode) & 0o111):
                    raise ValueError('executable-bit mismatch: '+key)
                with f.open('rb') as stream:
                    actual[key] = hashlib.file_digest(stream,'sha256').hexdigest()
    if actual != receipt['sha256']:
        raise ValueError('installed overlay missing, modified or stale; restage in a disposable checkout')
    return hashlib.sha256((expected/'source-receipt.json').read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--src',type=Path,required=True,help='prepared scratch Chromium src with reviewed overlay')
    inputs=ap.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--brave-core',type=Path,help='local Git repository containing the pinned commit')
    inputs.add_argument('--verified-staged-tree',type=Path,
                        help='exact stage created and hash-verified by regular RawS admission')
    ap.add_argument('--port1442', action='store_true',
                    help='run the sealed #1442 network/popup/scoped-cosmetic smoke')
    ap.add_argument('--args-file',type=Path,default=stage.HERE.parent/'ci/args.gn')
    args=ap.parse_args(); src=args.src.resolve(strict=True)
    if Path(stage.git(src,'rev-parse','--show-toplevel').decode().strip()).resolve()!=src:
        raise ValueError('--src must be the root of the dedicated Chromium checkout')
    if stage.git(src,'rev-parse','HEAD').decode().strip()!=stage.PINS['chromium']:
        raise ValueError('Chromium revision does not match RawS lock')
    settings=args.args_file.read_bytes()
    if hashlib.sha1(b'blob '+str(len(settings)).encode()+b'\0'+settings).hexdigest()!=ARG_BLOB:
        raise ValueError('not the reviewed RawS release/ARM64/Siso args.gn')
    gn = needed_tool('gn'); autoninja = needed_tool('autoninja')
    if args.verified_staged_tree:
        # CI's separate immutable production manifest verifies every staged and
        # installed byte before this runs. Compare again against its stage.
        receipt_hash=verify_tree(args.verified_staged_tree.resolve(strict=True),src)
    else:
        with tempfile.TemporaryDirectory(prefix='raws-source-verify-') as tmp:
            expected = Path(tmp)/'tree'
            stage.prepare(args.brave_core.resolve(strict=True), expected, stage.PINS['brave_core'])
            receipt_hash=verify_tree(expected,src)
    outroot=src/'out'
    if outroot.is_symlink(): raise ValueError('refusing symlinked out root')
    outroot.mkdir(exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='RawSHostSmoke-',dir=outroot))
    print('Diagnostic outputs (not a checkpoint):',out,flush=True)
    (out/'args.gn').write_bytes(settings)
    root_target = ROOT + ('1442' if args.port1442 else '')
    smoke_target = SMOKE + ('1442' if args.port1442 else '')
    rel=str(out.relative_to(src)); root='--root-target='+root_target
    def cmd(argv, capture=False):
        print('+', *argv, flush=True)
        return subprocess.run(argv,cwd=src,check=True,text=True,
                              stdout=subprocess.PIPE if capture else None).stdout
    cmd([gn,'gen',rel,root,'--fail-on-unused-args'])
    labels=cmd([gn,'desc',rel,root_target,'deps',root],True).splitlines()
    host=[x.strip() for x in labels if x.strip().startswith(smoke_target+'(')]
    if len(host)!=1: raise ValueError('host toolchain target not uniquely identified')
    tests = [(host[0], smoke_target.split(':', 1)[1], args.port1442)]
    if args.port1442:
        baseline = [x.strip() for x in labels if x.strip().startswith(SMOKE+'(')]
        if len(baseline) != 1:
            raise ValueError('Original RawS smoke target must still be present')
        tests.insert(0, (baseline[0], 'engine_smoke', False))
    graphs = []
    for label, _, _ in tests:
        graph=cmd([gn,'desc',rel,label,'deps','--all',root],True)
        dep_labels={x.strip().split('(')[0] for x in graph.splitlines()}
        for name in ('//brave/third_party/rust/adblock/v0_13:lib',
                     '//brave/components/brave_shields/core/common/adblock/rs:rust_lib'):
            if name not in dep_labels: raise ValueError('native dependency missing: '+name)
        graphs.append(label+'\n'+graph)
        cmd([gn,'check',rel,label,root])
    (out/'engine-graph.txt').write_text('\n'.join(graphs))
    cmd([autoninja,'-C',rel,root_target[2:]])
    hashes = {}
    for label, executable, port_cases in tests:
        outputs=cmd([gn,'desc',rel,label,'outputs',root],True).splitlines()
        candidates=[src/x.strip()[2:] for x in outputs if x.strip().startswith('//')
                    and Path(x.strip()).name==executable]
        if len(candidates)!=1: raise ValueError('ambiguous executable outputs: '+str(outputs))
        exe=candidates[0].resolve(strict=True)
        if out not in exe.parents: raise ValueError('executable outside new diagnostic output')
        result=cmd([str(exe)],True); print(result,end='')
        if port_cases:
            verify_port_output(result)
        else:
            verify_output(result)
        hashes[executable] = hashlib.sha256(exe.read_bytes()).hexdigest()
    (out/'engine-result.json').write_text(json.dumps({'scope':'host Rust/CXX only; not APK or device parity',
        'source_receipt_sha256':receipt_hash,'host_label':host[0],'pins':stage.PINS,
        'executable_sha256':hashes[smoke_target.split(':', 1)[1]], 'executables_sha256':hashes,
        'cases':list(CASES) + (['six-network', 'four-popup', 'scoped-hide',
                                'scoped-exception', 'incident1471-player-rules']
                               if args.port1442 else []),'apk_tested':False,'remote_execution_verified':False},indent=2)+'\n')

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError) as exc: sys.exit(str(exc))
