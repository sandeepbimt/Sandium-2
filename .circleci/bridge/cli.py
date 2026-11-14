"""Explicit local bridge orchestration; no CircleCI publication or discovery."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
from bridge import begin,capture,apply_chain,base_id,digest,encode


def atomic(path,value):
    path=Path(path);temp=path.with_suffix('.pending')
    temp.write_bytes(encode(value));os.replace(temp,path)


def run_bounded(command, timeout=1700):
    process=subprocess.Popen(command,start_new_session=True)
    try:
        code=process.wait(timeout=timeout)
        if code:raise subprocess.CalledProcessError(code,command)
    except BaseException:
        # Kill the full legacy Python/tar/zstd process group, not just its leader.
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:pass
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait()
        raise


MAX_LAYERS=7

def restore_chain(root, plan, legacy_script, timeout=1700):
    root=Path(root)
    if (root/'brave-work').exists() or (root/'brave-work').is_symlink():raise ValueError('Restore requires empty/disposable job tree')
    if len(plan['layers'])>MAX_LAYERS:raise ValueError(f'Checkpoint plan exceeds {MAX_LAYERS} incremental slots')
    raw=(root/'brave-workspace-checkpoint.manifest.json').read_bytes()
    if digest(raw)!=plan['base_manifest_sha256']:raise ValueError('Wrong original base manifest')
    manifest=json.loads(raw)
    if len(manifest.get('shards',[]))!=8:raise ValueError('Expected original eight-shard base')
    # Original restore verifies every compressed shard hash before extraction.
    run_bounded([sys.executable,'-u',str(legacy_script),'restore','--root',str(root)],timeout)
    head=base_id(raw)
    head=apply_chain(root/'brave-work',plan['layers'],head)
    if head!=plan['head']:raise ValueError('Incomplete chain')
    atomic(root/'.bridge-restored.json',dict(head=head,base=plan['base_manifest_sha256']))
    return head


def quiesce(script,root):
    spec=importlib.util.spec_from_file_location('legacy_shards',script)
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    from quiescence import ensure_quiescent
    ensure_quiescent(Path(root),mod)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=['restore-chain','begin','capture'])
    p.add_argument('--root',required=True,type=Path)
    p.add_argument('--legacy-script',required=True,type=Path)
    p.add_argument('--job',required=True)
    p.add_argument('--plan',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--trusted-local-filesystem',action='store_true')
    a=p.parse_args()
    if not a.trusted_local_filesystem:p.error('Trusted same-job filesystem assumption must be accepted')
    root=a.root.resolve();state=root/'.bridge-before.json';proof=root/'.bridge-restored.json'
    if a.phase=='restore-chain':
        if not a.plan:p.error('--plan required')
        restore_chain(root,json.loads(a.plan.read_text()),a.legacy_script.resolve())
    elif a.phase=='begin':
        quiesce(a.legacy_script.resolve(),root/'brave-work')
        restored=json.loads(proof.read_text())
        atomic(state,begin(root/'brave-work',restored['head'],a.job))
    else:
        if not a.output:p.error('--output required')
        (root/'.bridge-candidate.json').unlink(missing_ok=True)
        result=capture(root/'brave-work',json.loads(state.read_text()),a.job,a.output,
                       lambda:quiesce(a.legacy_script.resolve(),root/'brave-work'))
        atomic(root/'.bridge-candidate.json',result)
