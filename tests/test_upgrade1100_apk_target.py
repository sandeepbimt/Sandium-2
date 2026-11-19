import gzip,hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Target(unittest.TestCase):
 def test_exact_upstream_brave_target_and_profile(self):
  data=json.loads(gzip.decompress((ROOT/'tests/fixtures/upgrades158/apk-target.json.gz').read_bytes()))
  for row in data.values():
   b=row['text'].encode();self.assertEqual(hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),row['blob'])
  self.assertIn('group("brave") {\n  deps = [ "build/$target_os:brave" ]',data['BUILD.gn']['text'])
  android=data['build/android/BUILD.gn']['text'];self.assertIn('copy("brave") {',android);self.assertIn('deps += [ "//chrome/android:chrome_public_apk" ]',android);self.assertIn('outputs = [ brave_android_output ]',android)
  profile=json.loads((ROOT/'docs/upgrades/1.100.58/candidate-profile.json').read_text());self.assertEqual(profile['build']['target'],'brave');self.assertEqual(profile['build']['artifact'],'BraveMonoarm64.apk')
if __name__=='__main__':unittest.main()
