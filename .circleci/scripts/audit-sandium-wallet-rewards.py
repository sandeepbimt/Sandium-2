#!/usr/bin/env python3
"""Read-only pinned Android closure audit. Findings are blockers, not removal proof."""
import argparse
import json
import re
import subprocess
from pathlib import Path

PIN = '44a84b1f89d9a35287289d6a3d493e362f5a5123'
IMPORT = re.compile(r'^import\s+(org\.chromium\.(?:brave_wallet|brave_rewards|brave_ads)\.[\w.]+|org\.chromium\.chrome\.browser\.crypto_wallet\.[\w.]+);', re.M)
EXCLUSIVE_SOURCE = re.compile(r'"([^"\n]*(?:/crypto_wallet/|/BraveRewards[^/"\n]*|/rewards/)[^"\n]*\.java)"')

def audit(core):
    sha = subprocess.check_output(['git', '-C', str(core), 'rev-parse', 'HEAD'], text=True).strip()
    if sha != PIN:
        raise ValueError(f'pin mismatch: expected {PIN}, got {sha}')
    def read(relative):
        return subprocess.check_output(['git', '-C', str(core), 'show', sha+':'+relative], text=True)
    paths = ['android/brave_java_sources.gni', 'build/android/config.gni', 'browser/brave_ads/android/java_sources.gni']
    findings = []
    for relative in paths:
        for n, line in enumerate(read(relative).splitlines(), 1):
            if any(s in line for s in ('crypto_wallet/', 'BraveRewards', '/rewards/', 'brave_ads', 'brave_rewards')):
                findings.append({'path': relative, 'line': n, 'text': line.strip()})
    consumers = []
    files = subprocess.check_output(['git', '-C', str(core), 'ls-tree', '-r', '--name-only', sha, 'android/java'], text=True).splitlines()
    for relative in sorted(p for p in files if p.endswith('.java')):
        imports = IMPORT.findall(read(relative))
        if imports and '/crypto_wallet/' not in relative:
            consumers.append({'path': relative, 'imports': sorted(set(imports))})
    return {'pin': sha, 'status': 'audit_only_not_removal_proof',
            'required_gn_args_after_adaptation': {'enable_brave_wallet': False, 'enable_brave_rewards': False, 'enable_brave_ads': False},
            'source_list_candidates': findings, 'java_consumers': consumers,
            'caveat': 'Candidates include guarded entries. Resolve actual GN graph and compile Android before claiming exclusion.'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('core', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.core), indent=2))
    except (ValueError, subprocess.CalledProcessError) as e:
        parser.exit(2, str(e) + '\n')
