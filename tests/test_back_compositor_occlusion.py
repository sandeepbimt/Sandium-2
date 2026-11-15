"""Pinned source regression checks; not native C++ or device execution."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('back',ROOT/'.circleci/scripts/apply-sandium-back-transition.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class CompositorOcclusion(unittest.TestCase):
    def setUp(self):
        self.rel,self.old,self.new=next(c for c in m.CHANGES if c[0]=='cc/slim/layer_tree_impl.cc')
        self.source=(ROOT/'tests/fixtures/back-transition'/self.rel).read_text()
    def test_pinned_exact_one_guard_and_idempotence(self):
        result=m.transform(self.source,self.old,self.new)
        self.assertEqual(result,m.transform(result,self.old,self.new))
        self.assertEqual(result.replace(self.new,self.old,1),self.source)
    def test_unknown_anchor_fails_closed(self):
        with self.assertRaises(RuntimeError):m.transform(self.source.replace(self.old,'changed'),self.old,self.new)
    def test_effective_parent_opacity_not_only_local(self):
        self.assertIn('parent_opacity * layer.opacity() == 1.0f',self.new)
        self.assertIn('transform_new_pass_to_parent_target.Preserves2dAxisAlignment()',self.new)
    def test_internal_occlusion_and_quad_semantics_unchanged(self):
        result=m.transform(self.source,self.old,self.new)
        for marker in ['/*opacity=*/1.0f', 'occlusion_in_new_pass = data.occlusion_in_target;', 'parent_pass_occlusion.Union(occlusion_in_parent_target);', 'parent_opacity * layer.opacity()']:
            self.assertEqual(result.count(marker),self.source.count(marker)+(1 if marker=='parent_opacity * layer.opacity()' else 0))
    def test_guard_truth_table_model(self):
        # Model only: the C++ compositor test is still required.
        for parent,layer,axis,expected in [(1,1,True,True),(1,.5,True,False),(.5,1,True,False),(.5,.5,True,False),(1,0,True,False),(1,1,False,False)]:
            self.assertEqual(parent*layer==1 and axis,expected)
if __name__=='__main__':unittest.main()
