#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).with_name('apply-sandium-leo-removal.py');sp=importlib.util.spec_from_file_location('patch',p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_method_not_callsite(self):
  s='    if (isLeoEnabled()) { keep(); }\n    private boolean isLeoEnabled() { return true; }\n'
  self.assertEqual(m.method(s,'isLeoEnabled'),'    if (isLeoEnabled()) { keep(); }\n\n')
 def test_nested_blocks(self):self.assertEqual(m.block('prefix if (a) { if(b) {foo();} } suffix','if (a)'), 'prefix  suffix')
 def test_else_retains_normal_browsing(self):self.assertEqual(m.ifelse('if (a) { leo(); } else { normal(); }','if (a)',True),' normal(); ')
 def test_repeat_method_idempotent(self):
  s='    public void leo() { x(); }\n    public void normal() {}'
  r=m.method(s,'leo');self.assertEqual(r,m.method(r,'leo'));self.assertIn('normal()',r)
if __name__=='__main__':unittest.main()
