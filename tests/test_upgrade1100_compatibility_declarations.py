import gzip,hashlib,importlib.util,json,re,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads(gzip.decompress((ROOT/'tests/fixtures/upgrade1100/compatibility-declarations.json.gz').read_bytes()))
spec=importlib.util.spec_from_file_location('graph_audit',ROOT/'.circleci/scripts/audit-sandium-removal-graph.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Compatibility(unittest.TestCase):
 def test_exact_target_hash_guard_and_mutation_rejection(self):
  manifest=json.loads((ROOT/'.circleci/scripts/removal-compatibility-sources.json').read_text());self.assertEqual(manifest['reviewed_core_sha'],'bd6d26d1bced03c17a98baa86d2cd3425d543d1b');self.assertEqual(set(manifest['files']),set(DATA))
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary)
   for p,item in DATA.items():
    raw=item['text'].encode();self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),item['git_blob'])
    target=root/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
   self.assertEqual(m.verify_compatibility_sources(root),sorted(DATA))
   first=next(iter(DATA));(root/first).write_text(DATA[first]['text']+'\n// drift')
   with self.assertRaisesRegex(ValueError,'Compatibility source changed'):m.verify_compatibility_sources(root)
 def test_service_remains_interface_only_and_vpn_only_protocol(self):
  build=DATA['components/brave_ads/core/browser/service/BUILD.gn']['text']
  service=build.split('source_set("service") {',1)[1].split('source_set("test_support")',1)[0]
  sources=re.search(r'sources = \[(.*?)\]',service,re.S).group(1)
  self.assertEqual(re.findall(r'"([^"]+)"',sources),['ads_service.cc','ads_service.h','ads_service_callback.h','ads_service_observer.h'])
  deps=re.search(r'public_deps = \[(.*?)\]',service,re.S).group(1)
  self.assertEqual(set(re.findall(r'"([^"]+)"',deps)),{'//base','//brave/components/brave_ads/core/mojom','//brave/components/services/bat_ads/public/interfaces','//components/keyed_service/core','//mojo/public/cpp/bindings'})
  callback=DATA['components/brave_ads/core/browser/service/ads_service_callback.h']['text']
  self.assertEqual(re.findall(r'#include "([^"]+)"',callback),['base/functional/callback.h','brave/components/brave_ads/core/mojom/brave_ads.mojom-forward.h'])
  vpn=DATA['components/brave_vpn/common/mojom/brave_vpn.mojom']['text']
  self.assertIn('module brave_vpn.mojom;',vpn);self.assertIn('interface ServiceHandler {',vpn)
  self.assertIn('ReconnectToAgent();',vpn);self.assertNotIn('import ',vpn)
if __name__=='__main__':unittest.main()
