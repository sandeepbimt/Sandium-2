from pathlib import Path
import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('native_menu_adapter', ROOT/'experiments/native-menu/adapter.py')
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)

class NativeMenuAdapterTest(unittest.TestCase):
    def make_source(self, root):
        for path in (ADAPTER.HANDLER, ADAPTER.BUILD):
            target = root/path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((ADAPTER.HERE/'fixtures'/Path(path).name).read_text())

    def test_exact_preflight_replay_and_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.make_source(root)
            changes = ADAPTER.plan(root)
            self.assertEqual(7, len(changes))
            for path, text in changes.items():
                path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
            self.assertEqual(changes, ADAPTER.plan(root))
            handler = (root/ADAPTER.HANDLER).read_text()
            self.assertEqual(3, handler.count('mRawSMenu.dismissEditor();'))
            self.assertIn('mAppMenuDelegate.onOptionsItemSelected(\n                itemId, mDelegate.getBundleForMenuItem(model), triggeringMotion);', handler)
            self.assertIn('mModelList.addObserver(mListObserver);',handler)
            self.assertLess(handler.index('mRawSMenu.prepare'), handler.index('mModelList.addObserver'))
            self.assertIn('hideAppMenu();',handler)
            model = root/ADAPTER.JAVA/'RawSMenuModel.java'
            model.write_text('unreviewed module')
            with self.assertRaises(ValueError): ADAPTER.plan(root)

    def test_unknown_preimage_fails_before_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.make_source(root)
            original = (root/ADAPTER.HANDLER).read_text()
            (root/ADAPTER.BUILD).write_text('new upstream GN')
            with self.assertRaises(ValueError): ADAPTER.plan(root)
            self.assertEqual(original, (root/ADAPTER.HANDLER).read_text())
            self.assertFalse((root/ADAPTER.JAVA/'RawSNativeMenu.java').exists())

    def test_resources_and_native_boundaries(self):
        resources = ET.parse(ROOT/'sandium/menu/raws_menu.xml').getroot()
        names = {(node.attrib.get('type', node.tag), node.attrib['name']) for node in resources}
        self.assertEqual(len(resources), len(names))
        english = {n.attrib['name'] for n in resources if n.tag == 'string'}
        hindi = {n.attrib['name'] for n in ET.parse(ROOT/'sandium/menu/raws_menu_hi.xml').getroot()}
        self.assertEqual(english, hindi)
        code=(ROOT/'sandium/menu/java/org/chromium/chrome/browser/ui/appmenu/RawSNativeMenu.java').read_text()
        for forbidden in ('PopupWindow(', 'WindowManager', 'setTranslation', 'setHeight(', 'dispatchTouchEvent', 'loadUrl('):
            self.assertNotIn(forbidden,code)
        self.assertNotIn('nativeItems.clear();',code)
        self.assertIn('nativeSource.addObserver(nativeObserver)',code)
        self.assertIn('nativeSource.removeObserver(nativeObserver)',code)
        self.assertIn('if (catalog.containsKey(name)',code)
        self.assertIn('TaskTraits.USER_VISIBLE_MAY_BLOCK',code)
