#!/usr/bin/env python3
"""Compile actual descriptor call against pinned JSONReader declarations.
Other Chromium value/export headers are narrow stubs; no parser/runtime claim.
"""
import hashlib,pathlib,re,subprocess,tempfile,unittest
FEATURE=pathlib.Path(__file__).resolve().parents[1]
class JSONReaderCompile(unittest.TestCase):
 def test_required_strict_options(self):
  header=(FEATURE/'tests/fixtures/json_reader.h').read_bytes()
  self.assertEqual(hashlib.sha256(header).hexdigest(),'cc11fc68ff19fafde085c15349a2b6d17b09d21b4a75fc81c1e158eeee648548')
  source=(FEATURE/'native/element_color_renderer.cc').read_text()
  call=re.search(r'base::JSONReader::ReadDict\([^;]+;',source).group(0)
  self.assertEqual(call,'base::JSONReader::ReadDict(descriptor, base::JSON_PARSE_RFC);')
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d)
   files={'base/base_export.h':'#define BASE_EXPORT\n',
    'base/json/json_common.h':'#include <cstddef>\nnamespace base::internal {inline constexpr size_t kAbsoluteMaxDepth=200;}\n',
    'base/types/expected.h':'namespace base {template<class T,class E>class expected;}\n',
    'base/values.h':'namespace base {class Value{};class DictValue{};class ListValue{};}\n'}
   for path,text in files.items():
    p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
   (root/'base/json/json_reader.h').write_bytes(header)
   p=root/'call.cc';prefix='#include "base/json/json_reader.h"\nvoid f(std::string_view descriptor){auto parsed='
   p.write_text(prefix+call+'(void)parsed;}\n')
   cmd=['c++','-std=c++20','-Wall','-Wextra','-Werror','-fsyntax-only','-I'+str(root),str(p)]
   fixed=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(fixed.returncode,0,fixed.stderr)
   p.write_text(prefix+'base::JSONReader::ReadDict(descriptor);(void)parsed;}\n')
   old=subprocess.run(cmd,capture_output=True,text=True);self.assertNotEqual(old.returncode,0)
   self.assertIn('ReadDict',old.stderr)
if __name__=='__main__':unittest.main()
