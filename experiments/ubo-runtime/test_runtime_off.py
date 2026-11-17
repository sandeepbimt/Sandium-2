import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).parent
s=importlib.util.spec_from_file_location('runtime_off',ROOT/'verify_runtime_off.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
FEATURE='BASE_FEATURE(kBraveAndroidExtensions, base::FEATURE_DISABLED_BY_DEFAULT);'
def java(body=m.EXPECTED):return 'public boolean isEnabled(Profile profile) {'+body+'}'
class Tests(unittest.TestCase):
 def test_exact_gate(self):m.verify_text(java(),FEATURE)
 def test_unconditional_or_or_gate_rejected(self):
  for body in ['return true;',m.EXPECTED.replace('&&','||'),'return true;'+m.EXPECTED,m.EXPECTED.replace('&& org.chromium.ui.base.DeviceFormFactor.isNonMultiDisplayContextOnTablet(\n org.chromium.base.ContextUtils.getApplicationContext())','')]:
   with self.subTest(body=body),self.assertRaisesRegex(ValueError,'gate'):m.verify_text(java(body),FEATURE)
 def test_missing_duplicate_or_nested_gate_rejected(self):
  for content in ['',java()+java(),java('if (true) {return true;}'+m.EXPECTED)]:
   with self.subTest(content=content),self.assertRaisesRegex(ValueError,'gate'):m.verify_text(content,FEATURE)
 def test_enabled_missing_duplicate_feature_rejected(self):
  for features in ['',FEATURE+FEATURE,FEATURE.replace('DISABLED','ENABLED')]:
   with self.subTest(features=features),self.assertRaisesRegex(ValueError,'disabled'):m.verify_text(java(),features)
 def test_truth_table_contract_only_not_java_execution(self):
  # Explicit desired matrix; exact source-body check above binds its AND shape.
  for tablet,enabled,want in [(False,False,False),(False,True,False),(True,False,False),(True,True,True)]:
   self.assertEqual(enabled and tablet,want)
 def test_changed_loader_and_payload_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   src=Path(td);core=src/'brave'
   for p,text in [(src/m.JAVA,java()),(core/m.FEATURES,FEATURE)]:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
   with patch.object(m,'LOADERS',{}):
    m.verify(core,src)
    f=core/'resources/ubo/manifest.json';f.parent.mkdir(parents=True);f.write_text('{"name":"uBlock Origin"}')
    with self.assertRaisesRegex(ValueError,'manifest'):m.verify(core,src)
   with patch.object(m,'LOADERS',{m.FEATURES:'wrong'}):
    with self.assertRaisesRegex(ValueError,'loader'):m.verify(core,src)
if __name__=='__main__':unittest.main()
