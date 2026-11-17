#!/usr/bin/env python3
import hashlib,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def verify(root=ROOT, *, full=True):
 m=json.loads((root/'.circleci/x64-test/manifest.json').read_text())
 for section in ('inputs','outputs'):
  for path,digest in m[section].items():
   if hashlib.sha256((root/path).read_bytes()).hexdigest()!=digest:
    raise ValueError('Generated x64 pipeline drift: '+path)
 if (root/'.circleci/config.yml').read_bytes() != (root/'.circleci/x64-test/config.yml').read_bytes():
  raise ValueError('Active config differs from verified x64 config')
 if not full:
  print('X64_GENERATED_PIPELINE=PASS (stdlib integrity)')
  return
 spec=importlib.util.spec_from_file_location('x64build',root/'experiments/x64-test/build_config.py')
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 import yaml
 expected=mod.derive(yaml.safe_load((root/'.circleci/native-status-test/config.yml').read_text()))
 if yaml.safe_load((root/'.circleci/x64-test/config.yml').read_text())!=expected:raise ValueError('Config derivation mismatch')
 for path,text in mod.scripts(root).items():
  if (root/path).read_text()!=text:raise ValueError('Script derivation mismatch: '+path)
 print('X64_GENERATED_PIPELINE=PASS')
if __name__=='__main__':
 import sys
 # CI needs only artifact integrity; full deterministic derivation runs locally.
 # No implicit fallback: --derive explicitly requires the generation dependency.
 verify(full='--derive' in sys.argv)
