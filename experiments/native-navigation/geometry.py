"""Compose trace removal and reviewed native inset geometry without source writes."""
import importlib.util,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
native=load('native_status_geometry',ROOT/'.circleci/scripts/native-status-geometry.py')
trace=load('native_status_trace',ROOT/'.circleci/scripts/trace-sandium-back-geometry.py')
def plan(root):
 with tempfile.TemporaryDirectory(prefix='native-status-plan-') as td:
  stage=Path(td)
  for name in native.REVERSAL:
   text=(root/name).read_text()
   if name==trace.PATH:text=trace.reset(text)
   p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
  return {root/p.relative_to(stage):s for p,s in native.plan(stage, paint=False).items()}
