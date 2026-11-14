import importlib.util,tempfile,unittest,shutil,os,re
from pathlib import Path
spec=importlib.util.spec_from_file_location('patch',Path(__file__).with_name('apply-sandium-ntp-sponsored-removal.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
CORE=Path(os.environ.get('SANDIUM_PINNED_CORE',str(Path(__file__).resolve().parents[3]/'brave-core-audit')))
class Test(unittest.TestCase):
 def test_pinned_replay_and_preservation(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for p in m.PINS:
    (root/p).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(CORE/p,root/p)
   original={p:(root/p).read_text() for p in m.PINS};m.apply(root)
   output={p:(root/p).read_text() for p in m.PINS};m.apply(root)
   self.assertEqual(output,{p:(root/p).read_text() for p in m.PINS})
   gn=output[m.BASE+'BUILD.gn']
   for p in m.EXCLUDED:self.assertNotIn('"'+p+'.cc"',gn)
   self.assertIn('"ntp_background_images_component_installer.cc"',gn)
   self.assertIn('"brave_ntp_custom_background_service.cc"',gn)
   for path,names in ((m.BASE+'ntp_background_images_service.cc',('RegisterBackgroundImagesComponent','GetBackgroundImagesData','OnComponentReady','OnGetComponentJsonData')), (m.BASE+'view_counter_service.cc',('GetCurrentWallpaper','GetNextWallpaperForDisplay','CanShowBackgroundImages','ShouldShowCustomBackgroundImages'))):
    for name in names:
     def extract(text):
      hit=re.search(r'::'+name+r'\([^;]*?\)\s*(?:const\s*)?\{',text,re.S)
      self.assertIsNotNone(hit);start=hit.end()-1;end=start+1;depth=1
      while depth:
       depth+=(text[end]=='{')-(text[end]=='}');end+=1
      return text[start:end]
     self.assertEqual(extract(original[path]),extract(output[path]),name)
   self.assertNotIn('counts_reset_timer_.Start',output[m.BASE+'view_counter_model.cc'])
   self.assertNotIn('sponsored_images_update_check_timer_',output[m.BASE+'ntp_background_images_service.h'])
   self.assertIn('RegisterNTPBackgroundImagesComponent(',output[m.BASE+'ntp_background_images_service.cc'])
   self.assertNotIn('RegisterNTPSponsoredImagesComponent(',output[m.BASE+'ntp_background_images_service.cc'])
   self.assertNotIn('ads_service_->',output[m.BASE+'view_counter_service.cc'])
   self.assertNotIn('p3a_update_timer_.Start',output[m.BASE+'view_counter_service.cc'])
   self.assertIn('custom_background_service_->GetBackground()',output[m.BASE+'view_counter_service.cc'])
   self.assertIn('std::make_unique<NTPBackgroundImagesSource>(service)',output['browser/ntp_background/view_counter_service_factory.cc'])
 def test_drift_no_writes(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for p in m.PINS:
    (root/p).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(CORE/p,root/p)
   last=list(m.PINS)[-1];(root/last).write_text((root/last).read_text()+'\n// drift')
   before={p:(root/p).read_text() for p in m.PINS}
   with self.assertRaises(ValueError):m.apply(root)
   self.assertEqual(before,{p:(root/p).read_text() for p in m.PINS})
if __name__=='__main__':unittest.main()
