#!/usr/bin/env python3
"""NTP-only wallpaper-surround paint; requires proven native backing contract."""
from pathlib import Path
import argparse,json,subprocess
PIN='d331de35ca8ab1358c7a17e4bd41627d55eaef51'
BASE='chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/'
CHANGES=json.loads((Path(__file__).resolve().parents[1]/'features/homepage-surround/paint.json').read_text())
def plan(root):
    result={}
    for name,old,new in CHANGES:
        path=root/BASE/name;source=result.get(path,path.read_text())
        if source.count(new)==1 and old not in source.replace(new,'',1):result[path]=source;continue
        if source.count(old)!=1 or new in source:raise RuntimeError('homepage paint anchor mismatch: '+name)
        result[path]=source.replace(old,new,1)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source',type=Path);args=parser.parse_args()
    root=args.source.resolve()
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:raise RuntimeError('Chromium pin mismatch')
    result=plan(root)
    for path,text in result.items():path.write_text(text)
    print('HOMEPAGE_SURROUND_PAINT=APPLIED; native backing required')
if __name__=='__main__':main()
