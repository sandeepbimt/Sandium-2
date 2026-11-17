#!/usr/bin/env python3
"""Bounded allowlist export. Never copy unapproved trace names, args or log text."""
import argparse,json,math,re
from pathlib import Path
MAX_BYTES=64*1024*1024
MAX_EVENTS=5000
MAX_US=120_000_000
EVENTS={
'SandiumBackSnapshotAvailable','SandiumBackActivatedGeometry','SandiumBackActivatedControls',
'SandiumBackActivatedScroll','SandiumBackPreviewSelection','SandiumBackFallbackColor',
'SandiumBackPreviewBounds','SandiumBackHandoffState','SandiumBackParentOrigin',
'SandiumNativeBlurCapture','SandiumOrdinaryBlurSource','SandiumOrdinaryBlurBackground',
'SandiumOrdinaryBlurState','SandiumOrdinaryBlurExit','SandiumBlurOrigin',
'SandiumDarkPolicyPreferences','SandiumDarkPolicyCommit','SandiumDarkPolicyBFCache',
}
FIELDS={'navigation_id','state','reason','animate','native_pixels','outgoing_web','argb',
'incoming','depth','x','y','width','height','top_height','top_ratio','top_min_offset',
'entry_id','request_sequence','sequence','item_sequence_number','document_sequence_number',
'cache_hit','is_native','scroll_x','scroll_y','viewport_width','viewport_height',
'physical_width','physical_height','controls_height','bounds_width','bounds_height'}
JAVA_FIELDS={'sample','timeMs','stage','nativeWindowX','nativeWindowY','webWindowX','webWindowY',
'nativeY','webY','nativeScrollY','webScrollY','nativePaddingTop','webPaddingTop',
'nativeH','webH','nativeAttached','webAttached','overlap','syncTopHeight'}
def number(v):
 return isinstance(v,(int,float,bool)) and (not isinstance(v,float) or math.isfinite(v))
def matrix(v):
 # gfx transforms contain only numeric matrix representation. Reject arbitrary strings.
 if not isinstance(v,str) or len(v)>1024 or not re.fullmatch(r'[\d\s.,;\[\]()eE+\-]+',v):return None
 vals=re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',v)
 if not 6<=len(vals)<=16:return None
 out=[float(x) for x in vals]
 return out if all(math.isfinite(x) for x in out) else None
def safe_trace(events):
 out=[];first=None;dropped=0
 for e in events:
  if not isinstance(e,dict) or e.get('name') not in EVENTS:continue
  ts=e.get('ts')
  if not number(ts):continue
  if first is None:first=ts
  if ts<first or ts-first>MAX_US or len(out)>=MAX_EVENTS:dropped+=1;continue
  args=e.get('args',{});args=args if isinstance(args,dict) else {}
  safe={k:v for k,v in args.items() if k in FIELDS and number(v)}
  m=matrix(args.get('transform'))
  if m is not None:safe['matrix']=m
  out.append({'event':e['name'],'offset_us':ts-first,'args':safe,
              'correlation':'navigation_id' if 'navigation_id' in safe else 'unlinked'})
 return {'schema':1,'events':out,'truncated_events':dropped,'limits':{'events':MAX_EVENTS,'duration_s':120},
 'limitations':['No timestamp-only cross-process correlation.','Absent events do not prove a successful handoff or timeout.','Raw input may contain sensitive data; only this allowlisted output is sanitized.']}
def safe_logcat(lines):
 out=[]
 for line in lines:
  if 'SandiumCaptureOrigin' not in line:continue
  sample={}
  for k,v in re.findall(r'(\w+)=([^,\s]+)',line):
   if k not in JAVA_FIELDS:continue
   if v in ('true','false'):sample[k]=v=='true'
   else:
    try:n=float(v)
    except ValueError:continue
    if math.isfinite(n):sample[k]=n
  if 'sample' in sample and len(out)<MAX_EVENTS:out.append(sample)
 return {'schema':1,'capture_samples':out,'correlation':'Java-local sample only; not a native navigation ID'}
def main():
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--logcat',action='store_true');a=p.parse_args()
 if a.input.stat().st_size>MAX_BYTES:raise ValueError('Input exceeds 64 MiB safety limit')
 text=a.input.read_text()
 if a.logcat:result=safe_logcat(text.splitlines())
 else:
  data=json.loads(text);events=data.get('traceEvents',[]) if isinstance(data,dict) else data
  if not isinstance(events,list):raise ValueError('Expected Chrome trace JSON events; protobuf trace requires trusted conversion first')
  result=safe_trace(events)
 a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
if __name__=='__main__':main()
