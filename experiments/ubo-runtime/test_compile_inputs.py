import unittest
from verify_compile_inputs import check_shim,macro,require_response,require_schema_sources
class Tests(unittest.TestCase):
 def test_response(self):
  wrap=lambda v:{'//extensions/buildflags:buildflags':{'response_file_contents':v}}
  require_response(wrap(['ENABLE_EXTENSIONS=false','ENABLE_EXTENSIONS_CORE=true']))
  for value in [[],{},['ENABLE_EXTENSIONS_CORE=false'],['OTHER_ENABLE_EXTENSIONS_CORE=true'],['ENABLE_EXTENSIONS_CORE=true','ENABLE_EXTENSIONS_CORE=false']]:
   with self.subTest(value=value),self.assertRaises(ValueError):require_response(wrap(value))
 def test_schema_sources(self):
  values=['//out/android_Release_arm64/gen/extensions/common/api/scripts_internal.'+e for e in ('h','cc')]
  wrap=lambda v:{'//extensions/common/api:generated_api_types':{'sources':v}}
  require_schema_sources(wrap(values))
  for invalid in [[],values[:1],values+values, ['unrelated.h']]:
   with self.assertRaises(ValueError):require_schema_sources(wrap(invalid))
 def test_mutated_shim_rejected(self):
  with self.assertRaises(ValueError):check_shim(b'original Android-only stub')
 def test_generated_true(self):self.assertEqual(macro('#define BUILDFLAG_INTERNAL_ENABLE_EXTENSIONS_CORE() (1)\n'),['1'])
 def test_generated_false(self):self.assertEqual(macro('#define BUILDFLAG_INTERNAL_ENABLE_EXTENSIONS_CORE() (0)\n'),['0'])
 def test_missing(self):self.assertEqual(macro('#define OTHER() (1)'),[])
if __name__=='__main__':unittest.main()
