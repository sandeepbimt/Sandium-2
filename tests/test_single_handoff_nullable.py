"""#1388 regression: real generated qualified types with TYPE_USE-only Nullable."""
import pathlib, re, subprocess, tempfile, unittest
# Nullable.java is the unmodified Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51
# build/android/java/src/org/chromium/build/annotations/Nullable.java fixture.
ROOT = pathlib.Path(__file__).resolve().parents[1]

class NullablePlacement(unittest.TestCase):
    def test_generated_qualified_types_and_pre_fix_negative_mutation(self):
        sources = '\n'.join((ROOT / 'experiments/single-handoff' / name).read_text()
                            for name in ('home.py', 'java_adapter.py', 'holder_safety.py', 'holder_retention.py'))
        types = re.findall(r'\b((?:[a-zA-Z_]\w*\.)+@Nullable\s+\w+(?:<Boolean>)?)', sources)
        self.assertEqual(len(types), 16)
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            files = {
                'org/chromium/build/annotations/Nullable.java': (ROOT / 'experiments/single-handoff/fixtures/Nullable.java').read_text(),
                'android/view/ViewTreeObserver.java': 'package android.view; public class ViewTreeObserver {public interface OnPreDrawListener {}}',
                'org/chromium/chrome/browser/tab/NativePageHandoffOffer.java': 'package org.chromium.chrome.browser.tab; public class NativePageHandoffOffer {public static class Claim {}}',
                'org/chromium/chrome/browser/tab/Tab.java': 'package org.chromium.chrome.browser.tab; public interface Tab {}',
                'org/chromium/base/Callback.java': 'package org.chromium.base; public interface Callback<T> {}',
            }
            for path, content in files.items():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            def compile_types(values):
                (root / 'Harness.java').write_text(
                    'import org.chromium.build.annotations.Nullable;\n'
                    'class Harness {\n' + '\n'.join(f'private {t} field{i};' for i, t in enumerate(values)) + '\n}')
                return subprocess.run(['java', '--module', 'jdk.compiler/com.sun.tools.javac.Main',
                    '-d', str(root / 'classes'), *map(str, root.rglob('*.java'))], capture_output=True, text=True)
            fixed = compile_types(types)
            self.assertEqual(fixed.returncode, 0, fixed.stderr)
            old = compile_types(['@Nullable ' + t.replace('@Nullable ', '') for t in types])
            self.assertNotEqual(old.returncode, 0)
            self.assertIn('16 errors', old.stderr)
            self.assertIn('type-use annotation', old.stderr)

if __name__ == '__main__': unittest.main()
