#!/usr/bin/env python3
"""Reclaim only disposable local bootstrap copies in the isolated x64 job."""
import os
from pathlib import Path
import shutil
import subprocess
from contract import BRANCH, validate_graph

DISPOSABLE = (
 'brave-work/src/out/android_Release_arm64',
 'brave-workspace-checkpoint.shards',
 'brave-workspace-checkpoint.tar.zst',
 'brave-reference-ready.tar.zst',
)

def reclaim(root, branch):
 root=Path(root).resolve()
 if branch != BRANCH:raise ValueError('Reclaim is restricted to isolated x64 branch')
 validate_graph(root/'brave-work/src/out/android_Release')
 # Preflight ALL paths before deleting any. Never follow symlinked parents/targets.
 targets=[]
 for rel in DISPOSABLE:
  p=root/rel
  if any(part.is_symlink() for part in [p,*list(p.parents)[:len(Path(rel).parts)-1]]):
   raise ValueError('Refusing symlinked disposable path: '+rel)
  if p.resolve().is_relative_to(root) is False:raise ValueError('Path escapes job root')
  targets.append(p)
 before=shutil.disk_usage(root).free
 for p in targets:
  if p.is_dir():shutil.rmtree(p)
  elif p.exists():p.unlink()
 after=shutil.disk_usage(root).free
 print(f'X64_LOCAL_BOOTSTRAP_RECLAIM=PASS free_before={before} free_after={after} remote_caches=untouched',flush=True)

def require_archive_space(root):
 root=Path(root).resolve()
 # Conservative estimate: payload apparent size plus 5% tar/zstd overhead
 # and 1GiB reserve. Fail before an expensive pack instead of late ENOSPC.
 source=int(subprocess.check_output(['du','-sb',str(root/'brave-work')],text=True).split()[0])
 required=(source*105+99)//100+1024**3
 free=shutil.disk_usage(root).free
 print(f'X64_ARCHIVE_SPACE source_bytes={source} required_bytes={required} free_bytes={free}',flush=True)
 if free < required:raise ValueError('Insufficient disk for conservative x64 checkpoint estimate')

if __name__=='__main__':
 import sys
 root=Path(sys.argv[1])
 reclaim(root,os.environ.get('CIRCLE_BRANCH',''))
 if '--archive-space' in sys.argv:require_archive_space(root)
