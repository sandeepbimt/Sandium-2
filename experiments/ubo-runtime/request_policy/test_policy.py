import importlib.util,subprocess,tempfile,unittest,re,json
from pathlib import Path
HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('policy',HERE/'apply.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
CORE=Path('/workspace/scratch/40acbbeff193/brave-core-audit')
PIN=Path('/tmp/ubo-policy-src')
class Tests(unittest.TestCase):
 def test_fixed_identity_and_authoritative_calls(self):
  s=(HERE/'native_method.cc').read_text()
  for marker in ['extension_id != sandium_ubo::kExtensionId','Manifest::IsComponentLocation','extension->version().GetString() != sandium_ubo::kVersion','context->IsOffTheRecord()','crosses_incognito','GetAdControlType(map, first_party)','GetCosmeticFilteringControlType(map, first_party)','IsUboOwnerChosen(context)','SelectedOwnerGeneration(context)','request.web_request_type == WebRequestResourceType::MAIN_FRAME']:
   self.assertIn(marker,s)
  self.assertNotIn('GetSettingsForOneType',s)
  self.assertNotIn('SetContentSetting',s)
 def test_native_lists_authority_and_readiness(self):
  s=(HERE/'native_method.cc').read_text()
  for marker in ['kSandiumDefaultFilterListsMigrated', 'kAdBlockListSubscriptions', 'bool ready = migrated', 'sandium-subscriptions-only', 'if (enabled && !available) ready = false', 'crypto::SHA256HashString(*serialized)']:
   self.assertIn(marker,s)
  self.assertNotIn('GetFilterListCatalog',s)
  self.assertNotIn('kSandiumDefaultFilterListsSeeded',s)
  bridge=(HERE.parent/'shields_bridge/sandium_ubo_api.cc').read_text()
  self.assertIn('snapshot.Set("lists"',bridge)
  self.assertIn('*revision != args()[2].GetString()',bridge)
  self.assertIn('kSandiumDefaultFilterListsMigrated',bridge)
  self.assertIn('if (revision == list_revision_) return;',bridge)
  self.assertIn('&RuntimeState::InvalidateLists',bridge)
 def test_exact_native_apply_reset_and_both_dispatch_modes(self):
  inputs={
   'extensions/browser/api/extensions_api_client.h':Path('/tmp/ubo_extensions_api_client.h'),
   'extensions/browser/api/web_request/extension_web_request_event_router.h':PIN/'extensions/browser/api/web_request/extension_web_request_event_router.h',
   'extensions/browser/api/web_request/extension_web_request_event_router.cc':Path('/tmp/ubo_extension_web_request_event_router.cc')}
  if not all(p.exists() and p.stat().st_size for p in inputs.values()):self.skipTest('pinned native inputs not provisioned')
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)
   for name,p in inputs.items():
    f=src/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(p.read_bytes())
   for name in ['components/brave_shields/core/browser/ad_block_component_service_manager.h','components/brave_shields/core/browser/ad_block_component_service_manager.cc','browser/extensions/BUILD.gn','browser/extensions/api/brave_extensions_api_client.h','browser/extensions/api/brave_extensions_api_client.cc']:
    data=subprocess.check_output(['git','-C',str(CORE),'show','44a84b1f:'+name]);p=src/'brave'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
   for name, text in {
    'android/java/org/chromium/chrome/browser/shields/ContentFilteringFragment.java':'SANDIUM_FILTER_SUBSCRIPTIONS_ONLY',
    'components/brave_shields/core/common/pref_names.h':'kSandiumDefaultFilterListsMigrated',
    'components/brave_shields/content/browser/ad_block_subscription_service_manager.cc':'EnsureSandiumDefaultSubscriptions()'
   }.items():
    p=src/'brave'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
   subprocess.run(['git','apply','--include=browser/extensions/BUILD.gn','--whitespace=nowarn','-'],input=(HERE.parent/'brave-android-extensions.patch').read_bytes(),cwd=src/'brave',check=True,capture_output=True)
   baseline={str(p.relative_to(src)):p.read_bytes() for p in src.rglob('*') if p.is_file()}
   m.apply(src);first={str(p.relative_to(src)):p.read_bytes() for p in src.rglob('*') if p.is_file()}
   router=(src/'extensions/browser/api/web_request/extension_web_request_event_router.cc').read_text()
   self.assertEqual(router.count('ExtensionsAPIClient::Get()->AugmentWebRequestEventForExtension('),2)
   self.assertIn('browser_context, *request, listener->id.extension_id,',router)
   self.assertIn('browser_context, *request, key.extension_id,',router)
   m.apply(src);self.assertEqual(first,{str(p.relative_to(src)):p.read_bytes() for p in src.rglob('*') if p.is_file()})
   p=src/'brave/browser/extensions/api/brave_extensions_api_client.cc';b=p.read_bytes();p.write_bytes(b+b'foreign')
   with self.assertRaisesRegex(ValueError,'Unowned'):m.reset(src)
   p.write_bytes(b);m.reset(src);m.reset(src)
   self.assertEqual(baseline,{str(p.relative_to(src)):p.read_bytes() for p in src.rglob('*') if p.is_file()})
 def test_pinned_renderer_preserves_private_details(self):
  p=PIN/'extensions/renderer/resources/web_request_event.js'
  if not p.exists():self.skipTest('pinned renderer input not provisioned')
  s=p.read_text();start=s.index('function getFilteredDetails(');end=s.index('\n}',start)+2;fn=s[start:end]
  self.assertIn('utils.deepCopy(details)',fn)
  script='''const assert=require('node:assert/strict');
const utils={deepCopy: x=>structuredClone(x)};
function eraseHeaders(h){return h;}
function filterSecurityInfo(d){delete d.securityInfo;}
'''+fn+'''
const original={sandiumShields:{protocol:1,engineOwned:true,shieldsEnabled:false},requestHeaders:[{name:'Cookie',value:'x'}]};
const copied=getFilteredDetails(original,{droppedKeys:['requestHeaders'],hasExtraHeaders:false,hasSecurityInfoRawDer:false});
assert.deepEqual(copied.sandiumShields,original.sandiumShields);
assert.equal(copied.requestHeaders,undefined);
assert.notEqual(copied.sandiumShields,original.sandiumShields);
'''
  subprocess.run(['node','-e',script],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
