"""Characterize stale preference overwrite, not prove real browser event order.

Uses the actual BFCache/prerender blocks and actual preferences setter sequence.
The assertions intentionally demonstrate the unresolved defect surface.
"""
import json
from pathlib import Path
import runpy
import subprocess
import tempfile
here = Path(__file__).resolve().parent
activation = runpy.run_path(str(here / 'test_activation_native.py'))['src']
patches = json.loads((here / 'patches.json').read_text())
preference = next(p['new'] for p in patches if p['old'] ==
                 '  settings->SetForceDarkModeEnabled(prefs.force_dark_mode_enabled);')
preference = preference[preference.index('  TRACE_EVENT1'):]
source = activation[:activation.index('int main(){')]
source = source.replace('}void PR(', '}void Pref(Params prefs){auto* settings=&p.s;\n' + preference + '\n}void PR(')
transport = next(p['new'] for p in patches if 'out->sandium_dark_page_flags = data.' in p['new'])
transport = transport[transport.index('  out->sandium_dark_page_flags'): ]
source += 'struct Wire {int flag;int sandium_dark_page_flags(){return flag;}};\nvoid Decode(Wire data,Params* out){\n' + transport + '\n}\n'
source += r'''
int main(){
 for(int wire : {-2,-1,0,1}) {Params p;Decode({wire},&p);assert(p.sandium_dark_page_flags==wire);}
 for(int destination : {0,1}) {
  View v;Params target{destination}, stale{1-destination}, unmanaged{-1}, no_update{-2};
  v.BF(true,&target);assert(v.p.s.flag==destination);
  int untouched=v.p.s.invalidations;v.Pref(no_update);
  assert(v.p.s.flag==destination && v.p.s.invalidations==untouched);
  v.Pref(stale);assert(v.p.s.flag!=destination); // Late old-site preference wins.
  v.Pref(target);assert(v.p.s.flag==destination); // Later refresh fixes it.
  v.PR(&target);v.Pref(no_update);assert(v.p.s.flag==destination);
  v.Pref(unmanaged);assert(v.p.s.flag==-1);
  v.Pref(target);assert(v.p.s.flag==destination);
  // Matching repeats should be stable, with no extra invalidation.
  int count=v.p.s.invalidations;v.Pref(target);assert(v.p.s.invalidations==count);
 }
}
'''
source=source.replace('#include <cassert>', '#include <cassert>\n#include <initializer_list>')
with tempfile.TemporaryDirectory() as temp:
    path=Path(temp)/'ordering.cc';exe=Path(temp)/'ordering';path.write_text(source)
    subprocess.run(['c++','-std=c++20','-Wall','-Wextra','-Werror',str(path),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
print('Unmatched/no-update preserves BFCache and prerender ON/OFF; explicit unmanaged resets; live toggles remain. Stale matched policy is still a separate unproven race.')
