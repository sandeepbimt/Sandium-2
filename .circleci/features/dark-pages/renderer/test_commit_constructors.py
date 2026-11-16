"""Pinned positional Mojo caller regression. Not a Chromium compilation."""
import importlib.util
import pathlib
import re
import shutil
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('patcher', HERE / 'apply.py')
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)


def calls(text):
    # Pinned calls have Android-only data_url string. Count Android argument set.
    text = re.sub(r'#if (!?)BUILDFLAG\(IS_ANDROID\)\n(.*?)#endif',
                  lambda m: (m[2].split('#else')[1] if '#else' in m[2] else '')
                  if m[1] else m[2].split('#else')[0], text, flags=re.S)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    text = re.sub(r'//[^\n]*|^\s*#.*$', '', text, flags=re.M)
    text = text.replace('->', '__arrow__')
    result = []
    for match in re.finditer(r'CommitNavigationParams::New\s*\(', text):
        start = match.end(); depth = 0; angle = 0; args = []; pos = start
        for i in range(start, len(text)):
            char = text[i]
            if char in '([{': depth += 1
            elif char in ')]}':
                if char == ')' and depth == 0:
                    if text[pos:i].strip(): args.append(text[pos:i].strip())
                    result.append(args); break
                depth -= 1
            elif char == '<': angle += 1
            elif char == '>': angle -= 1
            elif char == ',' and depth == 0 and angle == 0:
                args.append(text[pos:i].strip()); pos = i + 1
        else: raise AssertionError('Unterminated constructor')
    return result


class ConstructorTest(unittest.TestCase):
    def test_four_exact_positional_callers_keep_all_prior_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / 'src'; shutil.copytree(HERE / 'fixtures', root)
            paths = ['content/browser/renderer_host/' + name for name in
                     ('navigation_entry_impl.cc', 'navigation_controller_impl.cc', 'navigation_request.cc')]
            before = [args for path in paths for args in calls((root / path).read_text())]
            self.assertEqual(len(before), 4)
            self.assertEqual([len(x) for x in before], [66] * 4)
            patcher.apply(root)
            after = [args for path in paths for args in calls((root / path).read_text())]
            self.assertEqual([len(x) for x in after], [67] * 4)
            for original, updated in zip(before, after):
                self.assertEqual(updated[0], '-1')
                self.assertEqual(updated[1:], original)
            self.assertEqual(patcher.apply(root), 0)
            for path in root.rglob('*.cc'):
                for args in calls(path.read_text()):
                    self.assertTrue(not args or args[0] == '-1', str(path))

if __name__ == '__main__': unittest.main()
