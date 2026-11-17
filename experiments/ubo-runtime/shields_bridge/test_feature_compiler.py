"""Exercise the exact pinned compiler's failing Parse/Validate path offline.

Only imports for file parsing and C++ emission are omitted: this test feeds a
Python dict to the UNMODIFIED upstream Feature parser/validators. It is not a
claim that C++ generation or native compilation has run.
"""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
import subprocess
import tempfile

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('bridge_apply', ROOT/'apply.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

class FeatureCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT/'testdata/pinned_feature_compiler.py').read_bytes()
        assert hashlib.sha256(source).hexdigest() == 'f0eabfd292119c2c5e99138d3d206291cf74c943c27a01021f1c0a4bfe2f08a3'
        tree = ast.parse(source)
        tree.body = [node for node in tree.body if not (
            isinstance(node, ast.ImportFrom) and node.module == 'code_util' or
            isinstance(node, ast.Import) and any(a.name == 'json_parse' for a in node.names))]
        ns = {'__name__': 'pinned_feature_compiler'}
        exec(compile(tree, '<pinned Chromium feature compiler>', 'exec'), ns)
        cls.Feature = ns['Feature']
        # Read exact production metadata from its AST, not a duplicate test dict.
        tree = ast.parse((ROOT/'apply.py').read_text())
        feature = next(node.value.args[0] for node in ast.walk(tree)
                       if isinstance(node, ast.Assign) and
                       any(isinstance(t, ast.Name) and t.id == 'feature' for t in node.targets))
        cls.definition = eval(compile(ast.Expression(feature), '<production feature>', 'eval'), {'ID_HASH': bridge.ID_HASH})

    def test_every_production_constraint_parses_and_validates(self):
        f = self.Feature('sandiumUbo')
        shared = {}
        f.Parse(self.definition, shared)
        f.Validate('APIFeature', shared)
        self.assertFalse(f.errors)
        self.assertNotIn('platforms', self.definition)
        self.assertEqual(self.definition['allowlist'], [bridge.ID_HASH])
        self.assertFalse(self.definition['component_extensions_auto_granted'])
        self.assertEqual(self.definition['contexts'], ['privileged_extension'])

    def test_actual_native_guard_rejects_non_android(self):
        cc = (ROOT/'sandium_ubo_api.cc').read_text()
        start = cc.index('bool IsTrustedComponent(')
        end = cc.index('\n}', start) + 2
        helper = cc[start:end]
        self.assertIn('#include "build/build_config.h"', cc)
        self.assertIn('#if !BUILDFLAG(IS_ANDROID)', helper)
        # Compile the exact helper, using minimal stand-ins only for its types.
        prefix = r'''#include <string>
#define BUILDFLAG(x) x
namespace sandium_ubo { const char* kExtensionId="fixed"; const char* kVersion="1.76.4"; }
struct Version { std::string text="1.76.4"; std::string GetString() const { return text; } };
struct Extension { std::string identity="fixed"; int where=1; Version ver; std::string id() const { return identity; } int location() const {return where;} Version version() const {return ver;} };
struct Manifest { static bool IsComponentLocation(int x) {return x==1;} };
'''
        for android in (0, 1):
            with tempfile.TemporaryDirectory() as d:
                source = Path(d)/'guard.cc'
                source.write_text(prefix + helper + '\nint main(){Extension e; if(IsTrustedComponent(&e) != ' + str(android) + ') return 1; if(IsTrustedComponent(nullptr))return 2; e.identity="other";if(IsTrustedComponent(&e))return 3;e.identity="fixed";e.where=0;if(IsTrustedComponent(&e))return 4;e.where=1;e.ver.text="wrong";if(IsTrustedComponent(&e))return 5;return 0;}')
                binary = Path(d)/'guard'
                subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',f'-DIS_ANDROID={android}',str(source),'-o',str(binary)],check=True)
                subprocess.run([str(binary)],check=True)

    def test_original_android_value_reproduces_build_failure(self):
        bad = copy.deepcopy(self.definition)
        bad['platforms'] = ['android']
        with self.assertRaisesRegex(AssertionError, 'Illegal value: "android"'):
            self.Feature('sandiumUbo').Parse(bad, {})

if __name__ == '__main__':
    unittest.main()
