#!/usr/bin/env python3
"""Offline composition; not production-wired until renderer and Android consumers land."""
import pathlib,argparse
ROOT=pathlib.Path(__file__).resolve().parent
FILES=['element_color_rule_store','element_color_session','element_color_transport']
def once(s,old,new):
 if new in s:return s
 if s.count(old)!=1:raise ValueError('Pinned anchor mismatch: '+old[:80])
 return s.replace(old,new,1)
def compose(root):
 edits={}
 def change(name,fn):
  p=root/name;edits[p]=fn(p.read_text())
 common='brave/components/cosmetic_filters/common/cosmetic_filters.mojom'
 def mojo(s):
  old='import "mojo/public/mojom/base/values.mojom";'
  s=once(s,old,old+'\nimport "mojo/public/mojom/base/unguessable_token.mojom";')
  fragment=(ROOT/'native/element_color_agent.mojom.fragment').read_text()
  if fragment not in s:s+='\n'+fragment
  return s
 change(common,mojo)
 def prefs(s):
  old='#include "brave/browser/brave_profile_prefs.h"'
  s=once(s,old,old+'\n#include "build/build_config.h"\n#if BUILDFLAG(IS_ANDROID)\n#include "brave/browser/sandium/element_color_rule_store.h"\n#endif')
  old='void RegisterProfilePrefs(user_prefs::PrefRegistrySyncable* registry) {'
  s=s.replace(old+'\n#include "build/build_config.h"\n#if BUILDFLAG(IS_ANDROID)',old+'\n#if BUILDFLAG(IS_ANDROID)')
  return once(s,old,old+'\n#if BUILDFLAG(IS_ANDROID)\n  sandium::ElementColorRuleStore::RegisterPrefs(registry);\n#endif')
 change('brave/browser/brave_profile_prefs.cc',prefs)
 def build(s):
  old='  sources = brave_chrome_browser_sources'
  names='\n'.join(f'      "sandium/{f}.{ext}",' for f in FILES for ext in ('cc','h'))
  names+='\n      "android/cosmetic_filters/sandium_element_colors_utils.cc",\n      "android/cosmetic_filters/sandium_element_colors_utils.h",'
  return once(s,old,old+'\n  if (is_android) {\n    sources += [\n'+names+'\n    ]\n  }')
 change('brave/browser/BUILD.gn',build)
 for name in FILES:
  for ext in ('cc','h'):
   p=f'{name}.{ext}';edits[root/'brave/browser/sandium'/p]=(ROOT/'native'/p).read_text()
 return edits
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source_root',type=pathlib.Path);a=p.parse_args()
 for path,data in compose(a.source_root).items():path.parent.mkdir(parents=True,exist_ok=True);path.write_text(data)
