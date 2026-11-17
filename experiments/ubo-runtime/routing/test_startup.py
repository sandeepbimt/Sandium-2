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
  for hook in ['OnExtensionUnloaded','OnExtensionHostRenderProcessGone','OnExtensionHostDestroyed','MarkRuntimeUnavailable','MustBlockAdRequest','GetHostsForExtension','IsRendererLive']:
   self.assertIn(hook,text)
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
  status=module('composed_visible_status',HERE.parent/'status/apply.py')
  names.update([status.JAVA,status.SETTINGS,status.NATIVE,status.LAYOUT,status.BUILD])
  names.update(['components/brave_shields/core/browser/ad_block_component_service_manager.h','components/brave_shields/core/browser/ad_block_component_service_manager.cc'])
  names.update(['browser/extensions/api/brave_extensions_api_client.h','browser/extensions/api/brave_extensions_api_client.cc'])
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
   # This isolated fixture composes runtime overlays, not the phone product
   # patches. Model their required source markers before recording baseline.
   for name,marker in {
    'android/java/org/chromium/chrome/browser/shields/ContentFilteringFragment.java':'SANDIUM_FILTER_SUBSCRIPTIONS_ONLY',
    'components/brave_shields/core/common/pref_names.h':'kSandiumDefaultFilterListsMigrated',
    'components/brave_shields/content/browser/ad_block_subscription_service_manager.cc':'EnsureSandiumDefaultSubscriptions()'
   }.items():
    p=core/name;p.parent.mkdir(parents=True,exist_ok=True)
    original=p.read_text() if p.exists() else ''
    p.write_text(original+'\n// Product fixture marker: '+marker+'\n')
   # Exercise the actual grouped-phone Shields product overlay, not only markers.
   popup=module('composed_phone_popup',HERE.parents[2]/'.circleci/scripts/apply-sandium-shields-popup.py')
   (core/status.JAVA).write_text(popup.java((core/status.JAVA).read_text()))
   (core/status.LAYOUT).write_text(popup.layout((core/status.LAYOUT).read_text()))
   loader.apply(src,Path('/tmp/ubo-prepared-1764.zip'))
   if bridge:bridge.apply(core)
   routing.apply(core)
   before={str(p.relative_to(core)):p.read_bytes() for p in core.rglob('*') if p.is_file()}
   startup.apply(core);startup.apply(core)
   # Validate all native/source layers together, not merely isolated fixtures.
   policy=module('final_request_policy',HERE.parent/'request_policy/apply.py')
   activation=module('final_activation',HERE.parent/'activation/apply.py')
   inputs={
    'extensions/browser/api/extensions_api_client.h':Path('/tmp/ubo_extensions_api_client.h'),
    'extensions/browser/api/web_request/extension_web_request_event_router.h':Path('/tmp/ubo-policy-src/extensions/browser/api/web_request/extension_web_request_event_router.h'),
    'extensions/browser/api/web_request/extension_web_request_event_router.cc':Path('/tmp/ubo_extension_web_request_event_router.cc')}
   for name,original in inputs.items():
    if not original.exists():self.fail('Missing pinned integration fixture: '+name)
    target=src/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(original.read_bytes())
   policy.apply(src);policy.apply(src)
   offline=module('full_offline_stage',HERE.parent/'offline_lists/apply.py')
   offline.apply(core);offline.apply(core)
   activation.verify(core,False)
   activation.apply(core,'experiment/ubo-runtime');activation.apply(core,'experiment/ubo-runtime')
   activation.verify(core,True)
   status.apply(core);status.apply(core)
   self.assertIn('sandium_engine_status',(core/status.LAYOUT).read_text())
   self.assertIn('"not_allowed"',(core/'components/sandium_ubo/sandium_ubo/manifest.json').read_text())
   status.reset(core);status.reset(core)
   activation.reset(core);offline.reset(core);offline.reset(core);policy.reset(src)
   if os.environ.get('UBO_ACTIVATION_SCRIPT'):
    activation=module('activation_stage',Path(os.environ['UBO_ACTIVATION_SCRIPT']))
    activation.apply(core,'experiment/ubo-runtime');activation.verify(core,True);activation.reset(core)
   factory=(core/'chromium_src/chrome/browser/extensions/component_loader_factory.cc').read_text()
   self.assertIn('IsRuntimeStartupAborted(profile_)',factory)
   startup.reset(core)
   self.assertEqual(before,{str(p.relative_to(core)):p.read_bytes() for p in core.rglob('*') if p.is_file()})
   routing.reset(core)
   if bridge:bridge.reset(core)
   loader.reset(src)
if __name__=='__main__':unittest.main()
