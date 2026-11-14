import importlib.util,json,subprocess,tempfile
from pathlib import Path
import argparse
a=argparse.ArgumentParser();a.add_argument('--other-features',type=Path,required=True);f=a.parse_args().other_features
paths=[f/'playlist-removal',f/'billing-origin-only',Path(__file__).resolve().parent]
mods=[];files=set()
for i,p in enumerate(paths):
 spec=importlib.util.spec_from_file_location('m'+str(i),p/'apply.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);mods.append(m)
 files.update(o['path'] for o in m.OPS)
with tempfile.TemporaryDirectory() as d:
 core=Path(d)
 for p in files:
  out=core/p;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(subprocess.check_output(['git','-C','/tmp/popup-brave-core','show','HEAD:'+p]))
 for m in mods:m.apply(core)
 before={p:(core/p).read_bytes() for p in files}
 for m in mods:m.apply(core)
 assert before=={p:(core/p).read_bytes() for p in files}
 print('PASS Playlist -> Billing -> News -> full replay byte-identical')
