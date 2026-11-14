import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
import yaml
ROOT = Path(__file__).resolve().parents[1]
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'.circleci/scripts'/f'{name}.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

class GraphPrecheck(unittest.TestCase):
    def test_graph_audit_is_in_real_build_not_separate_diagnostic_mode(self):
        c = yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
        self.assertNotIn('sandium-graph-precheck', c['jobs'])
        self.assertNotIn('run_graph_precheck', c['parameters'])
        for stage in range(1,6):
            text=json.dumps(c['jobs'][f'full-stage-{stage}'])
            self.assertIn('product-overlay-30-0.sh',text)
            self.assertLess(text.index('product-overlay-30-0.sh'),text.index('full-bounded-build.sh'))
        overlay=(ROOT/'.circleci/experimental-steps/product-overlay-30-0.sh').read_text()
        self.assertIn('precheck-graph.py --audits-only',overlay)
    def test_audit_failures_are_aggregated_not_skipped(self):
        calls=[]
        def run(command, check):
            calls.append(command)
            return types.SimpleNamespace(returncode=1 if 'audit-' in command[1] else 0)
        with self.assertRaisesRegex(RuntimeError, 'audit-sandium-leo'):
            module('precheck-graph').execute(ROOT,run)
        self.assertEqual(len(calls),5)
    def test_generation_failure_prevents_stale_audits(self):
        calls=[]
        def run(command, check):
            calls.append(command)
            if '--phase' in command:raise subprocess.CalledProcessError(1,command)
            return types.SimpleNamespace(returncode=0)
        with self.assertRaises(subprocess.CalledProcessError):module('precheck-graph').execute(ROOT,run)
        self.assertEqual(len(calls),2)
    def test_result_requires_current_success_marker_and_all_audits(self):
        m=module('precheck-graph-result');env={'CIRCLE_SHA1':'a'*40,'CIRCLE_BUILD_NUM':'123'}
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(m.write_result(temp,env=env)['status'],'FAILED_OR_INCOMPLETE')
            out=Path(temp)/'brave-apk'
            for name in m.REPORTS:(out/name).write_text('{"status":"PASS"}')
            self.assertEqual(m.write_result(temp,env=env)['status'],'FAILED_OR_INCOMPLETE')
            result=m.write_result(temp,True,env)
            self.assertEqual(result['status'],'PASS_GRAPH_ONLY');self.assertFalse(result['compiled']);self.assertFalse(result['apk_verified'])
            probe=out/'build-precheck';probe.mkdir()
            (probe/'build-precheck.json').write_text('{"status":"INCOMPLETE_TIMEOUT"}')
            result=m.write_result(temp,env=env)
            self.assertEqual(result['status'],'PASS_GRAPH_ONLY') # graph only
            self.assertEqual(result['selected_target_compile_status'],'INCOMPLETE_TIMEOUT')
            self.assertFalse(result['compiled']);self.assertFalse(result['full_build_verified'])
            env['CIRCLE_BUILD_NUM']='124'
            self.assertEqual(m.write_result(temp,env=env)['status'],'FAILED_OR_INCOMPLETE')
if __name__=='__main__':unittest.main()
