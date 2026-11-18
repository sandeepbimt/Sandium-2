from pathlib import Path
from unittest.mock import patch
import json, shutil, sys, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import ci_compile
class FeatureFingerprint(unittest.TestCase):
    def test_active_sources_change_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for path in ('upstream.lock.json','ci/args.gn','tools/ci_remote.py','tools/source_compat.py','tools/raw.py','tools/ci_official.py','tools/native_features.py','tools/ci_compile.py','tools/ci_source.py'):
                dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/path,dest)
            for path in ('sandium/features','sandium/menu','experiments/native-menu','experiments/native-toolbar','patches'):
                shutil.copytree(ROOT/path,root/path,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            with patch.object(ci_compile,'ROOT',root):
                baseline=ci_compile.fingerprint()
                manifest=root/'sandium/features/manifest.json'
                manifest.write_text(json.dumps({'schema':1,'features':['menu','toolbar']}))
                active=ci_compile.fingerprint();self.assertNotEqual(baseline,active)
                for path in ('sandium/menu/raws_menu.xml','experiments/native-toolbar/adapter.py','experiments/native-menu/grid_adapter.py'):
                    file=root/path;original=file.read_bytes();file.write_bytes(original+b'\n')
                    self.assertNotEqual(active,ci_compile.fingerprint())
                    file.write_bytes(original)
                self.assertEqual(active,ci_compile.fingerprint())
if __name__=='__main__':unittest.main()
