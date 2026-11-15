import importlib.util, unittest, tempfile, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('extras',ROOT/'.circleci/scripts/remove-sandium-packaged-extras.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Extras(unittest.TestCase):
 def test_pinned_idempotence_and_ownership(self):
  core=ROOT/'tests/fixtures/packaged-extras'
  for p in m.FILES:
   s=(core/p).read_text()
   out=m.transform(p,s)
   self.assertEqual(m.transform(p,out),out)
   if p=='BUILD.gn':
    self.assertNotIn('brave_vpn_confirm.json',out);self.assertNotIn('ntp_news_optin_icon_animation.json',out)
    self.assertIn('brave_first_party_storage_clean_animation.json',out)
   if p=='third_party/android_deps/BUILD.gn':
    self.assertNotIn('    ":com_wireguard_android_java",',out)
    self.assertIn('":com_github_bumptech_glide_java"',out)
   if p.endswith('AndroidManifest.xml'):
    self.assertNotIn('GoBackend$VpnService',out)
    self.assertIn('org.chromium.chrome.browser.vpn.wireguard.WireguardService',out) # separate existing VPN transform owns this
 def test_chromium_native_injection(self):
  patch=(ROOT/'tests/fixtures/packaged-extras/chrome-android-chrome_public_apk_tmpl.gni.patch').read_text()
  injected=next(line[1:] for line in patch.splitlines() if line.startswith('+') and '_wireguard_target =' in line)
  untouched='  loadable_modules += [ "other.so" ]\n'
  for line in (injected, injected.replace(' deps +=', '\n    deps +=').replace(' _libwireguard_dir =','\n    _libwireguard_dir =').replace(' loadable_modules +=','\n    loadable_modules +=')):
   output=m.transform_apk_template(untouched+line+'\n'+untouched)
   self.assertNotIn('wireguard',output)
   self.assertEqual(output.count('other.so'),2)
   self.assertEqual(output,m.transform_apk_template(output))
  with self.assertRaisesRegex(ValueError,'Residual WireGuard'):
   m.transform_apk_template(injected.replace('libwg-go.so','unexpected.so')+'\n')
 def test_wireguard_graph_edges(self):
  spec=importlib.util.spec_from_file_location('graph',ROOT/'.circleci/scripts/audit-sandium-removal-graph.py')
  g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
  for suffix in ('_java','_J__unpack_aar','_java__build_config'):
   label='//brave/third_party/android_deps:com_wireguard_android'+suffix
   self.assertIn(label,g.violations(label)['vpn'])
 def test_apk_payload_gate(self):
  spec=importlib.util.spec_from_file_location('audit',ROOT/'.circleci/scripts/audit-sandium-stripped-apk.py')
  a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
  for name in ('assets/brave_vpn_confirm.json','assets/ntp_news_optin_icon_animation.json','lib/arm64-v8a/libwg-go.so'):
   with tempfile.TemporaryDirectory() as td:
    apk=Path(td)/'a.apk'
    with zipfile.ZipFile(apk,'w') as z:z.writestr(name,'bad')
    with self.assertRaisesRegex(ValueError,'packaged payload'):a.audit(apk)
 def test_manifest_gate(self):
  spec=importlib.util.spec_from_file_location('audit',ROOT/'.circleci/scripts/audit-sandium-stripped-apk.py')
  a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
  for enc in ('utf-8','utf-16le'):
   with tempfile.TemporaryDirectory() as td:
    apk=Path(td)/'a.apk'
    with zipfile.ZipFile(apk,'w') as z:z.writestr('AndroidManifest.xml','android.permission.BIND_VPN_SERVICE'.encode(enc))
    with self.assertRaisesRegex(ValueError,'VPN manifest'):a.audit(apk)
if __name__=='__main__':unittest.main()
