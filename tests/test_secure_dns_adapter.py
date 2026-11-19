import gzip,hashlib,importlib.util,json,pathlib,tempfile,unittest
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
   adapter=m.load('adapter');target=root/adapter.BRIDGE;post=target.read_text();target.write_text(post+'//drift')
   with self.assertRaises(ValueError):m.execute(root,off=True)
   target.write_text(post);m.execute(root,off=True)
   self.assertEqual(before,{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()})
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
