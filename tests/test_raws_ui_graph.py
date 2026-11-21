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
JNI = '//chrome/android:chrome_jni_headers__action'
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
    JNI: 'inputs',
    JAVA + JAVAC: 'inputs',
    '//chrome/android:chrome_base_module_resources' + PREPARE: 'sources',
    '//chrome/android:chrome_public_apk_base_module_resources' + PREPARE: 'sources',
    '//chrome/android:new_tab_page_utils_java' + JAVAC: 'inputs',
    '//chrome/browser/feed/android:java' + JAVAC: 'inputs',
    RES + PREPARE: 'sources',
    MENU + ':java' + JAVAC: 'inputs',
    INTERNAL + ':java' + JAVAC: 'inputs',
    INTERNAL + ':java_resources' + PREPARE: 'sources',
    TOOLBAR + JAVAC: 'inputs',
    '//chrome/browser/ui/android/toolbar:java_resources' + PREPARE: 'sources',
    '//chrome/browser/ui/android/bottombar:config_java' + JAVAC: 'inputs',
    '//chrome/browser/ui/android/omnibox:java' + JAVAC: 'inputs',
}


class NativeUiGraph(unittest.TestCase):
    def responses(self):
        ui = graph.ui_source_targets()
        self.assertEqual(ACTIONS, {label: field for label, (field, paths) in ui.items()})
        response = {
            (APK, 'deps'): ENGINE + '\n' + '\n'.join('  ' + name for name in ACTIONS)
                           + '\n  //tools:helper(//build/toolchain/linux:clang_x64)\n',
            (JAVA, 'deps'): '  ' + RES + '\n',
            (TOOLBAR, 'deps'): '//chrome/browser/ui/android/toolbar:java_resources\n',
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
                    if name.startswith(('chrome/android/', 'chrome/browser/ui/android/',
                                        'chrome/browser/feed/android/'))
                    and name.endswith(('.java', '.xml', '.png', '.webp'))}
        self.assertEqual(intended, set().union(*(paths for field, paths in owners.values())))
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / 'graph.txt'
            args = self.invoke(self.responses(), receipt)
            self.assertIn(DARK, receipt.read_text())
            self.assertIn(JAVA + JAVAC, receipt.read_text())
            self.assertIn(JNI, receipt.read_text())
            self.assertEqual(1 + len(ACTIONS) + 3, len(args))
            self.assertNotIn((JAVA, 'sources'), [tuple(call.args[0][3:5]) for call in args])
            self.assertNotIn((RES, 'sources'), [tuple(call.args[0][3:5]) for call in args])

    def test_paged_presenter_contained_in_root_native_popup_not_native_flyout(self):
        files = json.loads((ROOT / 'raws-adblock/production-restore-recipe.json').read_text())['files']
        prefix = ('chrome/browser/ui/android/appmenu/internal/java/src/org/chromium/chrome/'
                  'browser/ui/appmenu/')

        def java(name):
            digest = files[prefix + name + '.java']['after_sha256']
            return (ROOT / 'raws-adblock/production-postimages' / digest).read_text()

        handler = java('AppMenuHandlerImpl')
        root_handler, flyout_handler = handler.split('public AppMenuPopup createAndShowFlyoutPopup(', 1)
        self.assertEqual(1, root_handler.count('mAppMenu.setSandiumModels('))
        self.assertIn('mModelList = mDelegate.getMenuItems();', root_handler)
        # Chromium opens on ACTION_DOWN even for an ordinary tap. The provisional
        # drag flag cannot decide whether the Sandium presenter is activated.
        self.assertIn('boolean useSandiumMenu = rawSMenuEligible() && mModelList != null;',
                      root_handler)
        self.assertIn('useSandiumMenu ? mModelList : null', root_handler)
        self.assertIn('onShow(startDragging && !useSandiumMenu)', root_handler)
        self.assertNotIn('!startDragging && rawSMenuEligible()', root_handler)
        self.assertNotIn('/* includeRawSGrid= */ true', handler)
        self.assertNotIn('setSandiumModels(', flyout_handler)
        self.assertIn('/* includeRawSGrid= */ false', flyout_handler)

        app_menu = java('AppMenu')
        main, flyout = app_menu.split('Creates, displays, and tracks a new flyout sub-menu.', 1)
        self.assertEqual(1, main.count('new SandiumPagedMenu('))
        self.assertEqual(1, main.count('popup.setContentView(contentView);'))
        self.assertLess(main.index('contentView = menu;'),
                        main.index('popup.setContentView(contentView);'))
        self.assertIn('mHierarchicalMenuController.setupFlyoutController(', main)
        self.assertIn('mSandiumMenu != menu', main)
        self.assertNotIn('new SandiumPagedMenu(', flyout)

        presenter = java('SandiumPagedMenu')
        self.assertNotIn('new PopupWindow', presenter)
        self.assertIn('entry.model != captured || !enabled(entry.model)', presenter)
        self.assertIn('handler.onItemClick(entry.model, null);', presenter)
        self.assertIn('.with(AppMenuItemProperties.MENU_ITEM_ID, 0)', presenter)
        self.assertIn('.with(AppMenuItemProperties.ENABLED, false)', presenter)

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
            for key in ((JAVA + JAVAC, 'inputs'), (JNI, 'inputs'), (JAVA, 'deps'),
                        (RES + PREPARE, 'sources'), (MENU + ':java' + JAVAC, 'inputs')):
                with self.subTest(key=key):
                    response = self.responses()
                    response[key] = response[key].replace(DARK, '') if key[1] == 'sources' else ''
                    with self.assertRaisesRegex(ValueError, 'APK graph lacks RawS UI (sources|resource dependency)'):
                        self.invoke(response, receipt)
                    self.assertFalse(receipt.exists())

    def test_missing_compiled_menu_presenter_or_donor_vector_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / 'graph.txt'
            for label, property_name, filename in (
                    (INTERNAL + ':java' + JAVAC, 'inputs', 'SandiumPagedMenu.java'),
                    (INTERNAL + ':java_resources' + PREPARE, 'sources',
                     'raws_sandium_menu_shred.xml')):
                with self.subTest(filename=filename):
                    response = self.responses()
                    key = (label, property_name)
                    response[key] = '\n'.join(line for line in response[key].splitlines()
                                               if not line.endswith('/' + filename))
                    with self.assertRaisesRegex(ValueError, 'APK graph lacks RawS UI sources'):
                        self.invoke(response, receipt)
                    self.assertFalse(receipt.exists())

    def test_original_engine_graph_does_not_need_ui(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(graph.subprocess, 'check_output', return_value=ENGINE) as desc:
            graph.verify_apk_graph(tmp, 'gn', 'out', {}, Path(tmp) / 'graph.txt')
            desc.assert_called_once()
