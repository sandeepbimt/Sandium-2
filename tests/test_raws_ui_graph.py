"""Exercise GN's pinned Android group/action split, not source-bearing fake groups."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import ci_prepare_raws_engine as graph

APK = '//chrome/android:chrome_public_apk'
JAVA = '//chrome/android:chrome_java'
RES = '//chrome/android:chrome_app_java_resources'
MENU = '//chrome/browser/ui/android/appmenu'
INTERNAL = MENU + '/internal'
TOOLBAR = '//chrome/browser/ui/android/toolbar:core_java'
JAVAC = '__compile_java'
PREPARE = '__prepare'
DARK = '//chrome/android/java/res/values-night/raws_main_settings_palette.xml'
ENGINE = '\n'.join(('//components/sandium_adblock:document_subresource_factory',
                    '//brave/third_party/rust/adblock/v0_13:lib',
                    '//chrome/browser:resources'))

# Source-backed by Chromium 52bdd217 rules.gni and internal_rules.gni:
# plain group targets have no sources; javac actions consume inputs;
# prepare_resources actions expose sources. The default GN toolchain's
# deps list uses unqualified labels, with explicit suffixes for other tools.
ACTIONS = {
    JAVA + JAVAC: 'inputs',
    RES + PREPARE: 'sources',
    MENU + ':java' + JAVAC: 'inputs',
    INTERNAL + ':java' + JAVAC: 'inputs',
    INTERNAL + ':java_resources' + PREPARE: 'sources',
    TOOLBAR + JAVAC: 'inputs',
}


class NativeUiGraph(unittest.TestCase):
    def responses(self):
        ui = graph.ui_source_targets()
        self.assertEqual(ACTIONS, {label: field for label, (field, paths) in ui.items()})
        response = {
            (APK, 'deps'): ENGINE + '\n' + '\n'.join('  ' + name for name in ACTIONS)
                           + '\n  //tools:helper(//build/toolchain/linux:clang_x64)\n',
            (JAVA, 'deps'): '  ' + RES + '\n',
            (INTERNAL + ':java', 'deps'): INTERNAL + ':java_resources\n',
        }
        for label, (field, paths) in ui.items():
            value = '\n'.join('  ' + x for x in sorted(paths))
            if field == 'inputs':
                value += '\n  //out/RawSandium/gen/some.build_config.json'
            response[label, field] = value
        return response

    def invoke(self, response, receipt):
        with patch.object(graph.subprocess, 'check_output',
                          side_effect=lambda argv, **kwargs: response[tuple(argv[3:5])]) as run:
            graph.verify_apk_graph(receipt.parent, 'gn', 'out', {}, receipt, require_ui=True)
            return run.call_args_list

    def test_every_manifest_ui_source_and_resource_checked_in_real_action_owner(self):
        owners = graph.ui_source_targets()
        files = json.loads((ROOT / 'raws-adblock/production-restore-recipe.json').read_text())['files']
        intended = {'//' + name for name in files
                    if name.startswith(('chrome/android/', 'chrome/browser/ui/android/'))
                    and name.endswith(('.java', '.xml'))}
        self.assertEqual(intended, set().union(*(paths for field, paths in owners.values())))
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / 'graph.txt'
            args = self.invoke(self.responses(), receipt)
            self.assertIn(DARK, receipt.read_text())
            self.assertIn(JAVA + JAVAC, receipt.read_text())
            self.assertEqual(1 + len(ACTIONS) + 2, len(args))
            self.assertNotIn((JAVA, 'sources'), [tuple(call.args[0][3:5]) for call in args])
            self.assertNotIn((RES, 'sources'), [tuple(call.args[0][3:5]) for call in args])

    def test_missing_action_or_host_only_action_cannot_pass(self):
        for alternate in ('', TOOLBAR + JAVAC + '(//build/toolchain/linux:clang_x64)'):
            with self.subTest(alternate=alternate), tempfile.TemporaryDirectory() as tmp:
                receipt = Path(tmp) / 'graph.txt'
                response = self.responses()
                response[APK, 'deps'] = response[APK, 'deps'].replace(TOOLBAR + JAVAC, alternate)
                with self.assertRaisesRegex(ValueError, 'APK graph lacks RawS UI actions'):
                    self.invoke(response, receipt)
                self.assertFalse(receipt.exists())

    def test_missing_actual_input_source_or_declared_resource_link_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / 'graph.txt'
            for key in ((JAVA + JAVAC, 'inputs'), (JAVA, 'deps'),
                        (RES + PREPARE, 'sources'), (MENU + ':java' + JAVAC, 'inputs')):
                with self.subTest(key=key):
                    response = self.responses()
                    response[key] = response[key].replace(DARK, '') if key[1] == 'sources' else ''
                    with self.assertRaisesRegex(ValueError, 'APK graph lacks RawS UI (sources|resource dependency)'):
                        self.invoke(response, receipt)
                    self.assertFalse(receipt.exists())

    def test_original_engine_graph_does_not_need_ui(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(graph.subprocess, 'check_output', return_value=ENGINE) as desc:
            graph.verify_apk_graph(tmp, 'gn', 'out', {}, Path(tmp) / 'graph.txt')
            desc.assert_called_once()
