import hashlib,importlib.util,json,os,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('archived_product',ROOT/'.circleci/upgrades/product.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ArchiveProof(unittest.TestCase):
 def graph(self,root):
  src=root/'brave-work/src';out=src/'out/android_Release_arm64';out.mkdir(parents=True)
  (out/'args.gn').write_text('import("args_generated.gni")\n')
  (out/'args_generated.gni').write_text('import("//brave/build/reviewed.gni")\n')
  imported=src/'brave/build/reviewed.gni';imported.parent.mkdir(parents=True);imported.write_text('is_official_build=true\n')
  (out/'build.ninja').write_text('rule verified\n')
  return src,out,imported
 def test_recursive_args_imports_bound(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);src,out,imported=self.graph(root);before=m.graph_hashes(root)
   self.assertIn('out/android_Release_arm64/args_generated.gni',before);self.assertIn('brave/build/reviewed.gni',before)
   imported.write_text('is_official_build=false\n');self.assertNotEqual(before,m.graph_hashes(root))
   (out/'args_generated.gni').unlink()
   with self.assertRaisesRegex(ValueError,'Missing regular GN'):m.graph_hashes(root)
 def test_dynamic_and_external_imports_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);src,out,imported=self.graph(root)
   for text,pattern in [('import("$unresolved/file.gni")\n','dynamic'),('import("../../../../../outside.gni")\n','escapes')]:
    (out/'args.gn').write_text(text)
    with self.assertRaisesRegex(ValueError,pattern):m.graph_hashes(root)
 def test_archived_graph_proof_independent_of_root_artifacts(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'CIRCLE_SHA1':'a'*40}):
   root=Path(d);(root/'brave-work/.sandium').mkdir(parents=True);reports=root/'brave-apk';reports.mkdir()
   recipe=root/'.circleci/features/removal-recipe.json';recipe.parent.mkdir(parents=True);recipe.write_text('{}')
   hashes={}
   for name in m.GRAPH_REPORTS:
    raw=json.dumps({'status':'PASS','scope':name}).encode();(reports/name).write_bytes(raw);hashes[name]=hashlib.sha256(raw).hexdigest()
   receipt={'schema':1,'source_revision':'a'*40,'recipe_sha256':hashlib.sha256(recipe.read_bytes()).hexdigest(),'reports':hashes}
   (reports/'removal-graph-receipt.json').write_text(json.dumps(receipt))
   m.persist_graph(root);before=m.graph_receipt(root);shutil.rmtree(reports)
   self.assertEqual(before,m.graph_receipt(root))
   (root/'brave-work/.sandium/product-graph/removal-native.json').write_text('{"status":"PASS"}')
   with self.assertRaisesRegex(ValueError,'Changed or failed'):m.graph_receipt(root)
if __name__=='__main__':unittest.main()
