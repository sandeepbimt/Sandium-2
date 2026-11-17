import tempfile,unittest,zipfile
from pathlib import Path
from contract import validate_apk,validate_graph,validate_handoff
class Contract(unittest.TestCase):
 def test_graph_rejects_arm(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'android_Release';p.mkdir();(p/'build.ninja').touch()
   for cpu,ok in [('arm64',False),('x64',True)]:
    (p/'args.gn').write_text(f'target_os = "android"\ntarget_cpu = "{cpu}"\nenable_android_secondary_abi = false\n')
    if ok:validate_graph(p)
    else:
     with self.assertRaises(ValueError):validate_graph(p)
 def test_apk_checks_actual_elf(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.apk'
   for machine,ok in [(183,False),(62,True)]:
    h=bytearray(20);h[:6]=b'\x7fELF\x02\x01';h[18:20]=machine.to_bytes(2,'little')
    with zipfile.ZipFile(p,'w') as z:z.writestr('lib/x86_64/libchrome.so',h)
    if ok:validate_apk(p)
    else:
     with self.assertRaises(ValueError):validate_apk(p)
 def test_handoff_rejects_foreign_arch_or_run(self):
  d=dict(TARGET='android-x64',BUILD_TYPE='Release',WORKFLOW_ID='w',REFERENCE_SOURCE_REVISION='r',STAGE='1')
  validate_handoff(d,'w','r',1)
  for key,value in [('TARGET','android-arm64'),('WORKFLOW_ID','other'),('REFERENCE_SOURCE_REVISION','old')]:
   with self.assertRaises(ValueError):validate_handoff(dict(d,**{key:value}),'w','r',1)
if __name__=='__main__':unittest.main()
