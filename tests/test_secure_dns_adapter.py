import gzip,hashlib,importlib.util,json,pathlib,re,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];D=ROOT/'experiments/secure-dns'
s=importlib.util.spec_from_file_location('dnsapply',D/'apply.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_pinned_composition_rollback_and_conflicts(self):
  fixture=json.loads(gzip.decompress((D/'fixtures/pinned.json.gz').read_bytes()))
  self.assertEqual(fixture['revision'],'d331de35ca8ab1358c7a17e4bd41627d55eaef51')
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td)
   for p,item in fixture['files'].items():
    b=item['source'].encode();self.assertEqual(hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),item['git_blob']);q=root/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
   native=m.load('default_mode');p=root/native.PATH;p.parent.mkdir(parents=True,exist_ok=True);p.write_text((D/'fixtures/default_dns_over_https_config_source.cc').read_text())
   before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
   m.execute(root);m.execute(root,True);m.execute(root)
   settings_path=m.load('adapter').SETTINGS
   upstream=fixture['files'][settings_path]['source']
   settings=(root/settings_path).read_text()
   references=lambda source:set(re.findall(r'\bR\.string\.(\w+)',source))
   # APK lint reported these as unused after the upstream screen was replaced.
   # Verify the production overlay retains their real Automatic/disabled states.
   required={
       'settings_automatic_mode_summary',
       'settings_secure_dns_disabled_for_managed_environment',
       'settings_secure_dns_disabled_for_parental_control',
   }
   self.assertTrue(required <= references(upstream) & references(settings))
   automatic=settings.split('private static String getProviderSummary',1)[1].split('private static String getManagedSummary',1)[0]
   self.assertRegex(automatic,r'if \("automatic"\.equals\(state\.providerId\)\) \{\s*return context\.getString\(R\.string\.settings_automatic_mode_summary\);')
   managed=settings.split('private static String getManagedSummary',1)[1].split('@Override',1)[0]
   self.assertLess(managed.index('!SandiumSecureDns.isReady()'),managed.index('SecureDnsBridge.getManagementMode()'))
   self.assertIn('SecureDnsBridge.isModeManaged()',managed)
   self.assertIn('SecureDnsBridge.isConfigManaged()',managed)
   self.assertRegex(managed,r'mode == SecureDnsManagementMode\.DISABLED_PARENTAL_CONTROLS\s*\? R\.string\.settings_secure_dns_disabled_for_parental_control\s*: R\.string\.settings_secure_dns_disabled_for_managed_environment')
   self.assertIn('choose.setSummary(managed ? getManagedSummary(context) : getProviderSummary(context, state));',settings)
   self.assertIn('choose.setEnabled(!managed);',settings)
   adapter=m.load('adapter');target=root/adapter.BRIDGE;post=target.read_text();target.write_text(post+'//drift')
   with self.assertRaises(ValueError):m.execute(root,off=True)
   target.write_text(post);m.execute(root,off=True)
   self.assertEqual(before,{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()})
 def test_effective_production_java_color_dependency(self):
  adapter=m.load('adapter')
  original=json.loads(gzip.decompress((D/'fixtures/pinned.json.gz').read_bytes()))['files'][adapter.GN]['source']
  actual=adapter.transform(adapter.GN,original)
  self.assertEqual(actual,adapter.transform(adapter.GN,actual))
  def java_target(s):return s.split('android_library("java") {',1)[1].split('\n  }',1)[0]
  def dependencies(s):return java_target(s).split('    deps = [',1)[1].split('    ]',1)[0]
  before=dependencies(original);after=dependencies(actual)
  dep='      "//components/browser_ui/styles/android:java",'
  self.assertNotIn(dep,before)
  self.assertEqual(after.count(dep),1)
  self.assertEqual(after.replace(dep+'\n',''),before)
  self.assertEqual(after.count('//third_party/android_deps:material_design_java'),1)
  ui=(ROOT/'android/java/org/chromium/chrome/browser/privacy/secure_dns/SandiumSecureDnsDropdown.java').read_text()
  self.assertNotIn('com.google.android.material.R',ui)
  self.assertIn('import org.chromium.components.browser_ui.styles.SemanticColorUtils;',ui)
  api=json.loads((D/'fixtures/semantic-colors-api.json').read_text())
  self.assertEqual(api['git_blob'],'57cdea3eae8187abdae4a3e7f0d723914a2122e7')
  self.assertEqual(api['methods'],{'getDefaultTextColorSecondary':'colorOnSurfaceVariant','getColorSurfaceContainer':'colorSurfaceContainer','getColorPrimary':'colorPrimary','getDefaultTextColor':'colorOnSurface'})
  for method in api['methods']:
   self.assertIn('SemanticColorUtils.'+method+'(getContext())',ui)
  # Adjacent DNS sources use their owned resource package, not the missing foreign R.
  for path in (D/'java').glob('*.java'):
   self.assertNotIn('com.google.android.material.R',path.read_text())
 def test_probe_and_policy_sources(self):
  facade=(D/'java/SandiumSecureDns.java').read_text();settings=(D/'java/SecureDnsSettings.java').read_text()
  self.assertIn('SecureDnsBridge.isConfigManaged()',facade)
  self.assertIn('SecureDnsBridge.isModeManaged()',facade)
  self.assertIn('SecureDnsManagementMode.NO_OVERRIDE',facade)
  self.assertNotIn('Settings.Secure',facade+settings);self.assertNotIn('Settings.Global',facade+settings)
  self.assertNotIn('return selectProvider("cloudflare")',facade)
  self.assertIn('new Thread(',settings);self.assertIn('generation[0]!=token',settings)
  self.assertIn('if(!isAdded() || !dialog.isShowing()',settings)
  self.assertIn('SetDefaultPrefValue',m.load('default_mode').NEW)
  self.assertNotIn('SandiumSecureDns.setEnabled(true)',settings)
  self.assertIn('R.string.text_off',settings)
  self.assertIn('return SecureDnsBridge.probeConfig(template)',facade)
  # Pure parser never selects a provider or mutates templates.
  native=m.load('adapter').transform(m.load('adapter').NATIVE,json.loads(gzip.decompress((D/'fixtures/pinned.json.gz').read_bytes()))['files'][m.load('adapter').NATIVE]['source'])
  body=native.split('JNI_SecureDnsBridge_ValidateConfig',1)[1].split('\n}',1)[0]
  self.assertNotIn('SetString',body)
if __name__=='__main__':unittest.main()
