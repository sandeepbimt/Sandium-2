import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('bridge_apply',ROOT/'apply.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
CORE=ROOT.parents[3]/'brave-core-audit'
# Worktree sibling fixture; real source, not generated interface assumptions.
CORE=Path('/workspace/scratch/40acbbeff193/brave-core-audit')
class BridgeTests(unittest.TestCase):
 def test_identity_restricted_capability(self):
  cc=(ROOT/'sandium_ubo_api.cc').read_text()
  self.assertIn('extension->id() == sandium_ubo::kExtensionId',cc)
  self.assertIn('Manifest::IsComponentLocation',cc)
  self.assertIn('extension->version().GetString() == sandium_ubo::kVersion',cc)
  self.assertIn('settings.Set("engineCutover", sandium_ubo::IsUboOwnerChosen',cc)
  self.assertIn('browser_context()->IsOffTheRecord()',cc)
  self.assertNotIn('SetAdControlType(',cc)
  self.assertNotIn('ExecuteJavaScript',cc)
 def test_compose_repeat_and_missing_identity_fail_closed(self):
  with tempfile.TemporaryDirectory() as d:
   c=Path(d)
   files=['common/extensions/api/api_sources.gni','common/extensions/api/_api_features.json','browser/extensions/api/BUILD.gn']
   for f in files:
    p=c/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((CORE/f).read_bytes())
   extra={
    'browser/extensions/resources.gni':'    "//brave/components/sandium_ubo:identity",',
    'chromium_src/chrome/browser/extensions/component_loader_factory.cc':'#include "brave/components/sandium_ubo/identity.h"\n  explicit BraveComponentLoader(Profile* profile) : ComponentLoader(profile) {}'
   }
   for f,text in extra.items():
    p=c/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
   before={f:(c/f).read_bytes() for f in files}
   with self.assertRaisesRegex(ValueError,'identity'):m.apply(c,include_bundle=False)
   self.assertEqual(before,{f:(c/f).read_bytes() for f in files})
   ident=c/'components/sandium_ubo/identity.h';ident.parent.mkdir(parents=True);ident.write_text(m.EXTENSION_ID)
   first=m.apply(c,include_bundle=False);second=m.apply(c,include_bundle=False);self.assertEqual(first,second)
   f=(c/'common/extensions/api/_api_features.json').read_text()
   self.assertIn(hashlib.sha1(m.EXTENSION_ID.encode()).hexdigest().upper(),f)
   self.assertIn('"component_extensions_auto_granted": false',f)
   m.reset(c)
   self.assertEqual(before,{f:(c/f).read_bytes() for f in files})
   self.assertFalse((c/'browser/extensions/api/sandium_ubo_api.cc').exists())
   m.apply(c,include_bundle=False)
   changed=c/'common/extensions/api/api_sources.gni';changed.write_text('user edit')
   with self.assertRaisesRegex(ValueError,'Unowned'):m.reset(c)
   self.assertEqual(changed.read_text(),'user edit')
 def test_background_hook_after_actual_listener_start(self):
  with tempfile.TemporaryDirectory() as d:
   c=Path(d);(c/'js').mkdir();(c/'manifest.json').write_text(json.dumps({'version':'1.76.4','manifest_version':2}))
   (c/'js/start.js').write_text('    µb.readyToFilter = true;\n    await initializeTabs();\n    webRequest.start();\n')
   m.patch_background(c);first=(c/'js/start.js').read_text();m.patch_background(c)
   self.assertEqual(first,(c/'js/start.js').read_text())
   self.assertLess(first.index("import('./sandium-bridge.js')"),first.index('µb.readyToFilter = true;'))
   self.assertLess(first.index('webRequest.start();'),first.index('reportListenersReady();'))
   self.assertIn('await startSandiumBridge(chrome.sandiumUbo, µb)',first)
 def test_changed_upstream_order_refused(self):
  with tempfile.TemporaryDirectory() as d:
   c=Path(d);(c/'js').mkdir();(c/'manifest.json').write_text(json.dumps({'version':'1.76.4','manifest_version':2}))
   (c/'js/start.js').write_text('    µb.readyToFilter = true;\n    webRequest.start();\n    await initializeTabs();\n')
   with self.assertRaisesRegex(ValueError,'ordering'):m.patch_background(c)
 def test_actual_popup_path_native_gate_and_stale_candidate(self):
  archive=Path('/tmp/ubo-prepared-1764.zip')
  if not archive.exists(): self.skipTest('pinned uBO fixture unavailable')
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'js').mkdir()
   with zipfile.ZipFile(archive) as z: source=z.read('js/tab.js').decode()
   (root/'js/tab.js').write_text(source)
   m.patch_popup_policy(root);patched=(root/'js/tab.js').read_text()
   m.patch_popup_policy(root);self.assertEqual(patched,(root/'js/tab.js').read_text())
   start=patched.index('    const popupCandidateTest = async function(')
   end=patched.index('\n    };',start)+7
   fn=patched[start:end]
   harness="""
const assert=require('node:assert/strict');
let allowed=true,closed=0,mutate=()=>{};
const candidate={opener:{tabId:1},destroy(){},launchSelfDestruction(){}};
const popupCandidates=new Map([[2,candidate]]);
const contexts=new Map([[1,{rawURL:'https://opener.test/'}],[2,{rawURL:'https://target.test/'}]]);
const µb={tabContextManager:{lookup(id){return contexts.get(id);}}};
const sandiumAllowsPopup=async()=>{mutate();return allowed;};
const onPopupUpdated=()=>{closed++;return true;};
"""+fn+"""
(async()=>{
await popupCandidateTest(2);assert.equal(closed,1);
allowed=false;await popupCandidateTest(2);assert.equal(closed,1);
allowed=true;mutate=()=>{contexts.get(2).rawURL='https://new.test/';};
await popupCandidateTest(2);assert.equal(closed,1);
mutate=()=>{popupCandidates.delete(2);};
await popupCandidateTest(2);assert.equal(closed,1);
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
   subprocess.run(['node','-e',harness],check=True)
 def test_schema_exact_functions(self):
  s=json.loads((ROOT/'sandium_ubo.json').read_text())[0]
  self.assertEqual([f['name'] for f in s['functions']],['getSettings','reportReady','getSettingsSnapshot','acknowledgeSettings','getTabPolicy'])
  self.assertNotIn('externally_connectable',json.dumps(s))
if __name__=='__main__':unittest.main()
