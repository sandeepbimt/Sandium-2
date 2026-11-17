import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('renderer_metrics',ROOT/'apply-renderer-metrics.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_pinned_fields(self):
  raw=(ROOT/'renderer-metrics-fixtures/page_load_metrics.mojom').read_text()
  for field in ['array<LayoutShift> new_layout_shifts','double layout_shift_score','bool after_input_or_scroll','TimeTicks layout_shift_time']:
   self.assertIn(field,raw)
 def test_replay_and_fail_closed(self):
  for filename,fn in [('metrics_web_contents_observer.cc',m.observer),('page_load_tracker.h',m.tracker)]:
   raw=(ROOT/'renderer-metrics-fixtures'/filename).read_text()
   out=fn(raw);self.assertEqual(out,fn(out))
   with self.assertRaises(ValueError):fn('wrong source')
 def test_observation_not_policy_and_no_content(self):
  raw=(ROOT/'renderer-metrics-fixtures/metrics_web_contents_observer.cc').read_text()
  out=m.observer(raw)
  self.assertLess(out.index(m.BLOCK),out.index('    tracker->UpdateMetrics('))
  for s in ['!render_data->new_layout_shifts.empty()', 'count > 0','std::isfinite','tracker == primary_page_.get()', 'GetSandiumDiagnosticNavigationId()', 'SandiumDiagnosticsEnabled']:
   self.assertIn(s,m.BLOCK)
  for s in ['GetURL','GetLastCommittedURL','GetTitle','innerText','EvaluateJavaScript']:
   self.assertNotIn(s,m.BLOCK)
if __name__=='__main__':unittest.main()
