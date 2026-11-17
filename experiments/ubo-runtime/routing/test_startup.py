import importlib.util,os,re,subprocess,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
CORE=Path('/workspace/scratch/40acbbeff193/brave-core-audit')
def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class Startup(unittest.TestCase):
 def test_bounded_and_strict_eligibility(self):
  text=(HERE/'startup.cc').read_text()
  for term in ['base::Seconds(12)','acknowledged_generation != eligibility.generation','!eligibility.user_rules_applied','!eligibility.policy_bridge_ready','!eligibility.listeners_reported','AcknowledgeOwnerSettings','loader->Remove(kExtensionId)','CancelDeferredNavigation']:
   self.assertIn(term,text)
  self.assertIn('!handle.GetURL().SchemeIsHTTPOrHTTPS()',text)
  self.assertLess(text.index('AbortRuntimeStartup(context);'),text.index('loader->Remove(kExtensionId)'))
  self.assertLess(text.index('loader->Remove(kExtensionId)'),text.index('MarkNativeFallbackComplete(context);'))
 def test_localized_source_lifecycle(self):
  loader_path=Path(os.environ.get('UBO_LOADER_SCRIPT',str(HERE.parent/'loader/apply.py')))
  if 'OnMaterialized' not in loader_path.read_text():self.skipTest('localized loader revision required')
  bridge_path=Path(os.environ.get('UBO_SHIELDS_SCRIPT',str(HERE.parent/'shields_bridge/apply.py')))
  bridge=module('shields_stage',bridge_path) if bridge_path.exists() else None
  loader=module('localized_loader',loader_path);routing=module('routing_stage',HERE/'apply.py');startup=module('startup_stage',HERE/'apply_startup.py')
  patch=(HERE.parent/'brave-android-extensions.patch').read_bytes()
  names=set(x.decode() for x in re.findall(rb'^\+\+\+ b/(.+)$',patch,re.M))
  names.update(loader.INPUTS)
  if bridge:names.update(['common/extensions/api/api_sources.gni','common/extensions/api/_api_features.json','browser/extensions/api/BUILD.gn'])
  names.update(['browser/net/brave_ad_block_tp_network_delegate_helper.cc','browser/net/brave_ad_block_csp_network_delegate_helper.cc','components/brave_shields/content/browser/domain_block_navigation_throttle.cc','browser/cosmetic_filters/cosmetic_filters_tab_helper.cc','browser/brave_content_browser_client.cc','components/cosmetic_filters/browser/cosmetic_filters_resources.h','components/cosmetic_filters/browser/cosmetic_filters_resources.cc','browser/sources.gni','components/brave_shields/content/browser/BUILD.gn','browser/brave_content_browser_client.cc'])
  with tempfile.TemporaryDirectory() as td:
   src=Path(td);core=src/'brave';core.mkdir()
   for name in names:
    r=subprocess.run(['git','-C',str(CORE),'show','44a84b1f:'+name],capture_output=True)
    if not r.returncode:
     p=core/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(r.stdout)
   subprocess.run(['git','apply','--whitespace=nowarn','-'],input=patch,cwd=core,check=True,capture_output=True)
   p=src/loader.NATIVE;p.parent.mkdir(parents=True);p.write_bytes(Path('/tmp/ubo-loader-pinned/chrome_component_extension_resource_manager.cc').read_bytes())
   subprocess.run(['git','apply','--whitespace=nowarn','-'],input=(core/'patches/chrome-browser-extensions-chrome_component_extension_resource_manager.cc.patch').read_bytes(),cwd=src,check=True,capture_output=True)
   loader.apply(src,Path('/tmp/ubo-prepared-1764.zip'))
   if bridge:bridge.apply(core)
   routing.apply(core)
   before={str(p.relative_to(core)):p.read_bytes() for p in core.rglob('*') if p.is_file()}
   startup.apply(core);startup.apply(core)
   factory=(core/'chromium_src/chrome/browser/extensions/component_loader_factory.cc').read_text()
   self.assertIn('IsRuntimeStartupAborted(profile_)',factory)
   startup.reset(core)
   self.assertEqual(before,{str(p.relative_to(core)):p.read_bytes() for p in core.rglob('*') if p.is_file()})
   routing.reset(core)
   if bridge:bridge.reset(core)
   loader.reset(src)
if __name__=='__main__':unittest.main()
