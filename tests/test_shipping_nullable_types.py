"""Guard qualified TYPE_USE annotations across shipping overlays, not only homepage."""
import importlib.util
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('branding', ROOT / '.circleci/scripts/apply-sandium-visible-branding.py')
BRANDING = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BRANDING)
class ShippingNullableTypes(unittest.TestCase):
    def test_footer_parameter_compiles_with_type_use_only_nullable(self):
        parameter = re.search(r'([^,\n]+ViewGroup container)', BRANDING.ABOUT_FOOTER).group(1).strip()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sources = {'Nullable.java': 'import java.lang.annotation.*; @Target(ElementType.TYPE_USE) @interface Nullable {}',
                       'android/view/ViewGroup.java': 'package android.view; public class ViewGroup {}',
                       'Probe.java': 'class Probe { void create(' + parameter + ') {} }'}
            for name, text in sources.items():
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
            command = ['java', '--module', 'jdk.compiler/com.sun.tools.javac.Main', '-d', str(root / 'classes')]
            result = subprocess.run(command + [str(root / name) for name in sources], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            (root / 'Probe.java').write_text('class Probe { void create(@Nullable android.view.ViewGroup container) {} }')
            result = subprocess.run(command + [str(root / name) for name in sources], capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
    def test_existing_footer_migrates_and_is_idempotent(self):
        old = BRANDING.ABOUT_FOOTER.replace('android.view.@Nullable ViewGroup', '@Nullable android.view.ViewGroup')
        repaired = BRANDING.compact_legal_footer(old)
        self.assertEqual(BRANDING.ABOUT_FOOTER, repaired)
        self.assertEqual(repaired, BRANDING.compact_legal_footer(repaired))
    def test_shipping_generated_content_has_no_package_prefix_annotation(self):
        # Scan generated strings/patches; compatibility-repair literals and negative tests
        # are intentionally excluded from the rule.
        failures = []
        for path in (ROOT / '.circleci').rglob('*'):
            if path.suffix not in ('.py', '.json', '.sh', '.java'): continue
            if path.name.startswith(('test-', 'test_')) or 'vendor' in path.parts: continue
            for line in path.read_text().splitlines():
                if "return about.replace('@Nullable android.view.ViewGroup container'" in line: continue
                if re.search(r'@(?:Nullable|NonNull)\s+(?:android|androidx|java|javax|org)\.', line):
                    failures.append(str(path.relative_to(ROOT)) + ': ' + line)
        self.assertEqual([], failures)
if __name__ == '__main__': unittest.main()
