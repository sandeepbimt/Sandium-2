import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('product_recipe',ROOT/'.circleci/scripts/product_recipe.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

sys.path.insert(0,str(ROOT/'.circleci/scripts'))
import apk_recipe
import product_absence

class Recipe(unittest.TestCase):
    def test_native_absence_contract(self):
        labels=['//brave/components/brave_talk/buildflags:buildflags','//brave/browser:browser']
        self.assertEqual(product_absence.check(labels,['talk'])['talk']['native_dependency_gate'],'pass')
        with self.assertRaises(ValueError):product_absence.check(labels+['//brave/components/brave_talk:brave_talk'],['talk'])
        with self.assertRaises(ValueError):product_absence.check([],['talk'])
        with self.assertRaises(ValueError):product_absence.check(labels,['leo'])

    def test_apk_proof_requires_success_and_detects_content_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'repo';shutil.copytree(ROOT,root,ignore=shutil.ignore_patterns('.git','__pycache__'))
            apk=root/'test.apk';apk.write_bytes(b'apk');proof=root/'proof.json';status=root/'status.txt';status.write_text('BUILD_EXIT_CODE=124\nBUILD_REASON=TIME_SLICE_COMPLETE\n')
            with self.assertRaises(ValueError):apk_recipe.record(root,apk,proof,status,'a'*40)
            status.write_text('BUILD_EXIT_CODE=0\nBUILD_REASON=BUILD_COMMAND_SUCCESS\nBUILD_COMMAND_SUCCEEDED=true\n')
            apk_recipe.record(root,apk,proof,status,'a'*40);apk_recipe.verify(root,apk,proof,'a'*40)
            apk.write_bytes(b'changed')
            with self.assertRaises(ValueError):apk_recipe.verify(root,apk,proof,'a'*40)
            apk.write_bytes(b'apk')
            with self.assertRaises(ValueError):apk_recipe.verify(root,apk,proof,'b'*40)

    def test_scope_and_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'repo';shutil.copytree(ROOT,root,ignore=shutil.ignore_patterns('.git','__pycache__'))
            a=p.identity(root);self.assertEqual(a,p.identity(root))
            file=root/'.circleci/scripts/apply-sandium-ui-prune.py';file.write_text(file.read_text()+'\n# implementation change\n')
            b=p.identity(root);self.assertEqual(a['compatibility'],b['compatibility']);self.assertNotEqual(a['recipe'],b['recipe'])
            manifest=root/'.circleci/product/recipe.json';data=json.loads(manifest.read_text());data['active_exclusions'].append('leo');manifest.write_text(json.dumps(data))
            c=p.identity(root);self.assertNotEqual(b['compatibility'],c['compatibility']);self.assertNotEqual(b['recipe'],c['recipe'])
    def test_pin_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'repo';shutil.copytree(ROOT,root,ignore=shutil.ignore_patterns('.git','__pycache__'))
            manifest=root/'.circleci/product/recipe.json';data=json.loads(manifest.read_text());data['pins']['brave']='a'*40;manifest.write_text(json.dumps(data))
            with self.assertRaises(ValueError):p.identity(root)

    def test_unproven_release_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'.circleci/product').mkdir(parents=True)
            data=p.load();data['release_ready']=True;(root/'.circleci/product/recipe.json').write_text(json.dumps(data))
            with self.assertRaises(ValueError):p.load(root)
    def test_active_bridge_guards_completion(self):
        code=(ROOT/'.circleci/bridge/driver.py').read_text()
        self.assertIn("p['recipe']==c.RECIPE",code)
        self.assertIn('recipe=c.RECIPE',code)
        self.assertIn('scope() + "-" + COMPAT',(ROOT/'.circleci/checkpoint/driver.py').read_text())

if __name__=='__main__':unittest.main()
