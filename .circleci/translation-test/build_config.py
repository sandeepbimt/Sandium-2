#!/usr/bin/env python3
"""Derive a branch-only translation test build without normal-reference writes."""
import copy
import hashlib
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
BRANCH = 'experiment/arm-translation-guard'
GUARD = 'python3 .circleci/scripts/apply-sandium-translation-guard.py "$CIRCLE_WORKING_DIRECTORY/brave-work/src"'


def derive(normal):
    cfg = copy.deepcopy(normal)
    cfg['jobs'].pop('renew-fixed-reference')
    cfg['workflows'].pop('fixed-reference-maintenance')
    job = cfg['jobs']['brave-android-staged-build']

    def isolate_steps(steps):
        result = []
        for source in steps:
            step = copy.deepcopy(source)
            if isinstance(step, dict) and 'save_cache' in step:
                key = step['save_cache']['key']
                # The sole writable caches are exact test-branch/workflow handoffs
                # and completion markers. Normal ARM base/metadata stay read-only.
                if not (key.startswith(('sandium-brave-handoff-v2-',
                                        'sandium-brave-apk-complete-v2-')) and
                        '{{ .Branch }}' in key and
                        '{{ .Environment.CIRCLE_WORKFLOW_ID }}' in key):
                    continue
            if isinstance(step, dict) and 'when' in step:
                step['when']['steps'] = isolate_steps(step['when']['steps'])
            if isinstance(step, dict) and 'store_artifacts' in step:
                artifact = step['store_artifacts']
                artifact['destination'] = 'sandium-arm-translation-test-only/' + artifact.get('destination', artifact['path']).lstrip('/')
            result.append(step)
            if isinstance(step, dict) and step.get('run', {}).get('command') == 'bash .circleci/experimental-steps/product-overlay-30-0.sh':
                result.append({'run': {
                    'name': 'Apply isolated ARM translation JNI compatibility experiment',
                    'command': 'set -euo pipefail\n' +
                        'test "${CIRCLE_BRANCH:-}" = "' + BRANCH + '"\n' + GUARD + '\n'}})
        return result

    job['steps'] = isolate_steps(job['steps'])
    # Compare the exact archive payload before source preparation/overlays run GN
    # and legitimately rewrite generated arguments or generated outputs. Keep the
    # strict comparison command intact: this is restore integrity, not a claim
    # that the subsequent product regeneration leaves every byte unchanged.
    steps = job['steps']
    captures = [step for step in steps if isinstance(step, dict) and
                step.get('run', {}).get('name') ==
                'Diagnose restored Siso checkpoint and compare prior stage']
    if len(captures) != 1:
        raise ValueError('Expected exactly one strict restore integrity capture')
    capture = captures[0]
    steps.remove(capture)
    prepare = next(i for i, step in enumerate(steps) if isinstance(step, dict) and
                   step.get('run', {}).get('name') == 'Prepare pinned Brave Android source')
    steps.insert(prepare, capture)
    for definition in cfg['workflows']['sandium-full-mode']['jobs']:
        definition['brave-android-staged-build']['filters'] = {'branches': {'only': BRANCH}}
    return cfg


def main():
    raw = yaml.safe_dump(derive(yaml.safe_load((ROOT / '.circleci/original-full/candidate.yml').read_text())), sort_keys=False, width=120)
    target = ROOT / '.circleci/translation-test'
    (target / 'config.yml').write_text(raw)
    (target / 'config.sha256').write_text(hashlib.sha256(raw.encode()).hexdigest() + '\n')
    (ROOT / '.circleci/config.yml').write_text(raw)


if __name__ == '__main__':
    main()
