#!/usr/bin/env python3
"""Observe exact constants shim and generated buildflag inputs before native compile.
No source edits, flags changes, output deletion, or runtime activation.
"""
import argparse, hashlib, json, os, re, subprocess
from pathlib import Path
SHIM='chromium_src/extensions/common/constants.h'
SHA='f979fbe8536c7e720cb8b0b654e7ebadd8b0ef820f4af9ad443b5d32f250d11c'
HEADER='gen/extensions/buildflags/buildflags.h'
def check_shim(data):
 actual=hashlib.sha256(data).hexdigest()
 if actual!=SHA:raise ValueError('EXT0 constants shim differs from reviewed postimage: '+actual)
def macro(text):
 values=re.findall(r'^#define\s+BUILDFLAG_INTERNAL_ENABLE_EXTENSIONS_CORE\(\)\s+\((\d+)\)',text,re.M)
 return values

def require_response(value):
 # GN JSON is keyed by the exact requested default-toolchain target.
 if not isinstance(value,dict) or set(value)!={'//extensions/buildflags:buildflags'}:
  raise ValueError('Unexpected GN target set')
 properties=value['//extensions/buildflags:buildflags']
 if not isinstance(properties,dict) or set(properties)!={'response_file_contents'}:
  raise ValueError('Unexpected GN buildflag property set')
 value=properties['response_file_contents']
 # No substring match: unrelated flags or contradictory duplicates fail.
 if not isinstance(value,list) or not all(isinstance(x,str) for x in value):
  raise ValueError('Unexpected GN buildflag response-file shape')
 flags=[x for x in value if x.startswith('ENABLE_EXTENSIONS_CORE=')]
 if flags not in (['ENABLE_EXTENSIONS_CORE=true'],['ENABLE_EXTENSIONS_CORE=1']):
  raise ValueError('EXT0 generator action does not request enabled extension core: '+repr(flags))

def require_schema_sources(value):
 target = '//extensions/common/api:generated_api_types'
 if not isinstance(value,dict) or set(value)!={target}:
  raise ValueError('Unexpected generated API target')
 properties=value[target]
 if not isinstance(properties,dict) or set(properties)!={'sources'}:
  raise ValueError('Unexpected generated API source properties')
 sources=properties['sources']
 if not isinstance(sources,list) or not all(isinstance(x,str) for x in sources):
  raise ValueError('Unexpected generated API sources')
 for suffix in ('/gen/extensions/common/api/scripts_internal.h','/gen/extensions/common/api/scripts_internal.cc'):
  if sum(x.endswith(suffix) for x in sources)!=1:
   raise ValueError('Missing/duplicate scripts_internal generated type: '+suffix)

def inspect(src, require_generated=False):
 core=src/'brave';out=src/'out/android_Release_arm64'
 p=core/SHIM;data=p.read_bytes()
 print('EXT0_CONSTANTS_SHIM_SHA256='+hashlib.sha256(data).hexdigest(),flush=True)
 print('EXT0_CONSTANTS_SHIM_PREFIX='+repr(data.decode().splitlines()[:22]),flush=True)
 check_shim(data)
 header=out/HEADER
 values=macro(header.read_text()) if header.is_file() else []
 print('EXT0_GENERATED_CORE_FLAG='+json.dumps(values),flush=True)
 if require_generated and values!=['1']:
  raise ValueError('EXT0 compiled buildflag is not ENABLE_EXTENSIONS_CORE=1')
 if not require_generated:
  env=os.environ.copy()
  env['PYTHONPATH']=os.pathsep.join(str(src/p) for p in ('brave/script','tools/grit/grit/extern','brave/vendor/requests','build','brave/vendor/depot_tools'))+os.pathsep+env.get('PYTHONPATH','')
  r=subprocess.run([str(src/'buildtools/linux64/gn'),'desc',str(out),'//extensions/buildflags:buildflags','response_file_contents','--format=json'],cwd=src,env=env,text=True,capture_output=True)
  print('EXT0_BUILDFLAG_RESPONSE_CONTENTS='+r.stdout,flush=True)
  if r.returncode:raise ValueError(r.stderr)
  require_response(json.loads(r.stdout))
  # Pinned json_schema_api.gni generated_types exposes BOTH generated .cc/.h
  # as static_library sources through get_target_outputs(schema_generator).
  r=subprocess.run([str(src/'buildtools/linux64/gn'),'desc',str(out),'//extensions/common/api:generated_api_types','sources','--format=json'],cwd=src,env=env,text=True,capture_output=True)
  if r.returncode:raise ValueError(r.stderr)
  require_schema_sources(json.loads(r.stdout))
  print('EXT0_SCRIPTS_INTERNAL_TYPES=DECLARED_IN_GENERATED_API_TYPES',flush=True)
 print('EXT0_COMPILE_INPUT_GATE=PASS '+('generated' if require_generated else 'source-and-action')+'; runtime not validated',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--src',type=Path,required=True);p.add_argument('--require-generated',action='store_true');a=p.parse_args();inspect(a.src.resolve(),a.require_generated)
