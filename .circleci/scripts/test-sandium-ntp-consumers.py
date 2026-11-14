import importlib.util,tempfile,unittest,shutil,os
from pathlib import Path
spec=importlib.util.spec_from_file_location('m',Path(__file__).with_name('apply-sandium-ntp-consumers.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
CORE=Path(os.environ.get('SANDIUM_PINNED_CORE',str(Path(__file__).resolve().parents[3]/'brave-core-audit')))
class Test(unittest.TestCase):
 def test_apply_replay_preserve_normal(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for p in m.FILES:
    (root/p).parent.mkdir(parents=True,exist_ok=True);shutil.copy(CORE/p,root/p)
   m.apply(root);first={p:(root/p).read_text() for p in m.FILES};m.apply(root);self.assertEqual(first,{p:(root/p).read_text() for p in m.FILES})
   self.assertIn('CreateWallpaper(*data)',first[m.FILES[0]])
   original=(CORE/m.FILES[0]).read_text()
   def ordinary_body(text):
    begin=text.index('NTPBackgroundImagesBridge::CreateWallpaper(')
    end=text.index('\n}',begin)+2
    return text[begin:end]
   self.assertEqual(ordinary_body(original),ordinary_body(first[m.FILES[0]]))
   java=first['android/java/org/chromium/chrome/browser/ntp_background_images/NTPBackgroundImagesBridge.java']
   self.assertIn('return new BackgroundImage(imagePath, 0, 0, new ImageCredit(author, link));',java)
   self.assertIn('setBackgroundImage(mNtpImageGlobal)',first['android/java/org/chromium/chrome/browser/ntp/BraveNewTabPageLayout.java'])
   self.assertNotIn('RecordViewedAdEvent',first[m.FILES[0]])
   self.assertNotIn('RecordClickedAdEvent',first[m.FILES[0]])
   self.assertNotIn('new_tab_takeover/android:new_tab_takeover',first['browser/sources.gni'])
   self.assertNotIn('new_tab_takeover_generated.pak',first['components/resources/BUILD.gn'])
 def test_drift_fails_before_write(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for p in m.FILES:
    (root/p).parent.mkdir(parents=True,exist_ok=True);shutil.copy(CORE/p,root/p)
   p=root/'browser/sources.gni';p.write_text(p.read_text().replace('new_tab_takeover/android:new_tab_takeover','new_tab_takeover/android:changed'))
   first=(root/m.FILES[0]).read_text()
   with self.assertRaises(ValueError):m.apply(root)
   self.assertEqual(first,(root/m.FILES[0]).read_text())
if __name__=='__main__':unittest.main()
