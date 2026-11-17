"""Regression evidence for why the candidate remains dormant.

These arithmetic counterexamples are not Blink execution tests and do not certify
any solution. They prevent documenting either rejected heuristic as sufficient.
"""
import unittest

class KnownMetricBlockers(unittest.TestCase):
    def test_fixed_representation_loses_lineheight_provenance(self):
        scale = 1.25
        # Parent 16px -> rendered 20px. ConvertLineHeight flattens 150% to 30px.
        from_percent = 16 * scale * 1.5
        from_authored_fixed = 30
        self.assertEqual(from_percent, from_authored_fixed)
        # Child 1lh must not scale the already-scaled percentage again.
        self.assertEqual(from_percent / scale * scale, 30)
        # But authored fixed30px must receive child's selected size multiplier.
        self.assertEqual(from_authored_fixed * scale, 37.5)
        # A Length-only heuristic receives identical inputs yet needs two outputs.
        self.assertNotEqual(30, 37.5)

    def test_glyph_metric_input_can_apply_factor_twice(self):
        scale = 1.25
        baseline_xheight = 8
        parent_metric = baseline_xheight * scale
        naive_child_2ex = 2 * parent_metric * scale
        one_scale_reference = 2 * baseline_xheight * scale
        self.assertEqual(naive_child_2ex,25)
        self.assertEqual(one_scale_reference,20)
        self.assertNotEqual(naive_child_2ex,one_scale_reference)

    def test_animation_bypass_makes_homogeneous_assumption_unsafe(self):
        scale = 1.25
        authored = 24
        converter_only = authored * scale
        direct_animation_setter = authored
        self.assertNotEqual(converter_only,direct_animation_setter)
        # Dividing both by site scale cannot restore the same reference metric.
        self.assertNotEqual(converter_only/scale,direct_animation_setter/scale)

if __name__ == '__main__': unittest.main()
