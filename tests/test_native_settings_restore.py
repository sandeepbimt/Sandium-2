"""Pinned Settings restoration and pure geometry, no Android-runtime claim."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
fade=load('fade_restore','.circleci/scripts/apply-sandium-settings-fade.py')
theme=load('theme_restore','.circleci/scripts/apply-sandium-native-theme.py')
restore=load('settings_restore','experiments/native-navigation/settings.py')
geometry=load('geometry_restore','experiments/native-navigation/geometry.py')
scroll=load('scroll_restore','.circleci/scripts/apply-sandium-scroll-status-bar.py')
opaque=load('opaque_restore','.circleci/scripts/opaque-status-paint.py')
class Restore(unittest.TestCase):
 def sources(self):
  native=(ROOT/'.circleci/tests/fixtures/settings-fade/SettingsActivity.java').read_text()
  brave=(ROOT/'.circleci/tests/fixtures/motion/BraveSettingsActivity.java').read_text()
  styled=theme.settings_surface(brave)
  return {fade.SETTINGS:(native,fade.settings(native)),
          'brave/'+fade.BRAVE_SETTINGS:(styled,fade.brave(theme.settings_surface(theme.settings_motion(brave))))}
 def test_exact_native_motion_keeps_theme(self):
  for path,(expected,changed) in self.sources().items():
   suffix='\n// unrelated wallpaper/address styling remains\n'
   actual=restore.transform(path,changed+suffix)
   self.assertEqual(actual,expected+suffix)
   self.assertNotIn('sandium_settings_fade',actual)
   self.assertNotIn('view.animate()',actual)
 def test_drift_fail_closed_no_writes(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for path,(_,changed) in self.sources().items():
    p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(changed)
   target=root/('brave/'+fade.BRAVE_SETTINGS)
   target.write_text(target.read_text().replace('sandiumConfigureWindowFade();','wrongCall();'))
   before={p:p.read_text() for p in root.rglob('*.java')}
   with self.assertRaises(RuntimeError):restore.plan(root)
   self.assertEqual(before,{p:p.read_text() for p in before})
 def test_native_geometry_preserves_opaque_paint_no_gradient(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);expected={}
   for name,path in scroll.FILES.items():
    base=(ROOT/'.circleci/tests/fixtures/status-bar'/name).read_text()
    # Current product has already removed scroll geometry and applied opaque paint.
    text=opaque.transform(path,base)
    p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);expected[p]=text
   self.assertEqual(geometry.plan(root),expected)
   for text in geometry.plan(root).values():self.assertNotIn('mSandiumTopProtectionHeight',text)
if __name__=='__main__':unittest.main()
