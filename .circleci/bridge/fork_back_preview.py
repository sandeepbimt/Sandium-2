#!/usr/bin/env python3
"""One frozen, metadata-only import; never mutate foreign receipts/dependencies.

The source cache is restored read-only by CircleCI. Its exact identity was
verified after #1166's successful native cache save/readback. The first normal
build still restores/checks every referenced payload before compilation.
"""
import copy
import json
import os
from pathlib import Path
import sys
import time
import driver as d

SOURCE_SCOPE = 'sandium-exp-single-v1-bridge-crash01'
TARGET_SCOPE = 'sandium-exp-single-v1-bridge-backpreview01'
TARGET_BRANCH = 'experiment/sandium-back-transition'
SOURCE_ID = '49ada219fa9cdb4df7b5a2a694cd5d5e23c15b23873f195de7ed34c72ee3e7aa'
SOURCE_COMMIT = '379837c136b79902ea1a07ad0a1455b1435e0c06'
SOURCE_WORKFLOW = 'e25623ab-de77-41be-bc8c-7d2b2ff1b7b8'
SOURCE_CACHE_KEY = 'sandium-experimental-head-v1-UHElyZWl7v4t+BDNIuwsl8ERHc8_YdW6aI8Kz55sxTY=-Kii3RVq+Ku7mFo7d3L6X2KAZuhk9feAAx1hdflFR_d4='


def verify_source(receipt, now, pipeline, expected_id=SOURCE_ID):
    p = receipt['payload']
    if receipt['id'] != expected_id or d.bridge.digest(d.bridge.encode(p)) != expected_id:
        raise ValueError('Frozen source receipt identity/integrity mismatch')
    if (p['scope'],p['kind'],p['compatibility'],p['source'],p['workflow']) != (
            SOURCE_SCOPE,d.KIND,d.c.COMPAT,SOURCE_COMMIT,SOURCE_WORKFLOW):
        raise ValueError('Frozen source provenance mismatch')
    if p['pipeline'] != 1166 or p['pipeline'] > pipeline:
        raise ValueError('Unexpected or older target pipeline')
    plan = p['plan']; base = plan['base']; layers = plan['layers']
    if len(layers) != 1:
        raise ValueError('Expected exact refreshed one-layer source plan')
    expected = base['id']
    for layer in layers:
        if layer['parent'] != expected:
            raise ValueError('Broken source chain')
        expected = layer['id']
    if plan['head'] != expected:
        raise ValueError('Wrong source plan head')
    for record in [base]+layers:
        if record['expires_at'] <= now:
            raise ValueError('Expired source dependency')
        if not record['key'].startswith(SOURCE_SCOPE+'-'):
            raise ValueError('Unexpected foreign payload key')
    return p


def marker(env):
    return {key:env[key] for key in ('CIRCLE_SHA1','CIRCLE_WORKFLOW_ID','SANDIUM_PIPELINE_NUMBER')}


def gate(env):
    if env.get('CIRCLE_BRANCH') != TARGET_BRANCH or env.get('SANDIUM_EXPERIMENT_SCOPE') != TARGET_SCOPE:
        raise ValueError('Only dedicated back-preview branch/scope may import')
    if env.get('SANDIUM_ALLOW_SEED_IMPORT') != 'true' or env.get('SANDIUM_STAGE') != '0':
        raise ValueError('Explicit stage-zero seed import required')
    d.gate()


def make_seed(receipt, env, now, expected_id=SOURCE_ID):
    source = verify_source(receipt,now,int(env['SANDIUM_PIPELINE_NUMBER']),expected_id)
    p = dict(kind=d.KIND,scope=TARGET_SCOPE,compatibility=d.c.COMPAT,
             source=env['CIRCLE_SHA1'],pipeline=int(env['SANDIUM_PIPELINE_NUMBER']),
             workflow=env['CIRCLE_WORKFLOW_ID'],stage=0,apk_verified=False,
             previous_receipt=None,plan=copy.deepcopy(source['plan']),
             seed_import=dict(receipt_id=receipt['id'],scope=source['scope'],
                              source=source['source'],workflow=source['workflow']))
    return dict(id=d.bridge.digest(d.bridge.encode(p)),payload=p)


def prepare():
    gate(os.environ)
    if d.HEAD.exists():
        raise ValueError('Seed cannot replace an existing target head')
    if (d.STATE/'back-seed-target-absent.json').exists():
        raise ValueError('Stale prepare marker; fresh initializer job required')
    d.c.save(d.STATE/'back-seed-target-absent.json',marker(os.environ))


def import_seed():
    gate(os.environ)
    if d.c.read(d.STATE/'back-seed-target-absent.json') != marker(os.environ):
        raise ValueError('Missing or stale target-absence proof')
    # At this point HEAD is the exact source cache restored by YAML, not a
    # writable source namespace. Validate everything before changing local files.
    receipt = d.c.read(d.HEAD)
    candidate = make_seed(receipt,os.environ,time.time())
    d.valid(candidate)
    d.c.save(d.STATE/'back-seed-source-receipt.json',receipt)
    d.c.save(d.STATE/'candidate.json',candidate)
    d.c.save(d.STATE/'back-seed-report.json',dict(
        source_receipt=receipt['id'],target_receipt=candidate['id'],
        target_scope=TARGET_SCOPE,plan_unchanged=True,payloads_verified_this_job=False,
        expiry=min(x['expires_at'] for x in [receipt['payload']['plan']['base']]+receipt['payload']['plan']['layers'])))
    # Remove only disposable locally restored source receipt files. Remote
    # source cache is never deleted, replaced, refreshed or published here.
    d.HEAD.unlink()
    (d.HEAD.parent/'previous-receipt.json').unlink(missing_ok=True)
    (d.STATE/'back-seed-target-absent.json').unlink()
    print('BACK_PREVIEW_SEED=PREPARED; normal restore must verify payloads')

if __name__ == '__main__':
    {'prepare':prepare,'import':import_seed}[sys.argv[1]]()
