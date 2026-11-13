import importlib.util
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('usage',ROOT/'.circleci/scripts/apply-sandium-usage-removal.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class UsageRemoval(unittest.TestCase):
    def fixture(self,core):
        java=core/m.JAVA;java.parent.mkdir(parents=True);java.write_text('class Fixture {\n'+''.join(m.REMOVALS[m.JAVA])+'        String getSafeBrowsingApiKey();\n}\n')
        build=core/'browser/brave_stats/BUILD.gn';build.parent.mkdir(parents=True);build.write_text((ROOT/'tests/fixtures/usage/BUILD.gn').read_text())
        cpp=core/m.CPP;cpp.parent.mkdir(parents=True);cpp.write_text((ROOT/'tests/fixtures/usage/brave_init_android.cc').read_text())
    def test_removes_bridge_idempotently_preserves_safe_browsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            core=Path(tmp);self.fixture(core);m.apply(core);first={p:p.read_bytes() for p in (core/m.JAVA,core/m.CPP,core/'browser/brave_stats/BUILD.gn')};m.apply(core)
            self.assertEqual(first,{p:p.read_bytes() for p in first})
            self.assertNotIn('StatsUpdater',(core/m.CPP).read_text());self.assertIn('GetSafeBrowsingApiKey',(core/m.CPP).read_text())
    def test_partial_drift_refused_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            core=Path(tmp);self.fixture(core);p=core/m.JAVA;p.write_text(p.read_text().replace(m.REMOVALS[m.JAVA][0],''));original=(core/m.CPP).read_bytes()
            with self.assertRaises(ValueError):m.apply(core)
            self.assertEqual(original,(core/m.CPP).read_bytes())
    def test_wired_before_gn_and_continuation(self):
        source=(ROOT/'.circleci/scripts/prepare-brave-source.sh').read_text()
        self.assertEqual(source.count('apply-sandium-usage-removal.py'),2)
        self.assertLess(source.index('apply-sandium-usage-removal.py'),source.index('pnpm run build Release'))
        self.assertIn('--gn enable_brave_stats_updater:false',source)

if __name__=='__main__':unittest.main()
