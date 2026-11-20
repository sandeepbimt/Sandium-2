import hashlib,json,sys,tempfile,unittest,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import native_smoke as smoke

class NativeEvidenceGate(unittest.TestCase):
    def test_partial_success_not_accepted(self):
        text='\n'.join(['ok '+k for k in smoke.CASES]+['RAWS_ENGINE_SMOKE_V2_PASS'])+'\n'
        smoke.verify_output(text)
        for bad in ['RAWS_ENGINE_SMOKE_V2_PASS\n', text.replace('ok exception\n',''),text+'ok extra\n']:
            with self.assertRaises(ValueError): smoke.verify_output(bad)

    def test_source_gate(self):
        with tempfile.TemporaryDirectory() as t:
            ref=Path(t)/'ref'; installed=Path(t)/'installed'
            for folder in ['brave', 'components/sandium_adblock']:
                (ref/folder).mkdir(parents=True); (ref/folder/'input').write_bytes(b'x')
            shutil.copytree(ref,installed)
            (ref/'source-receipt.json').write_text(json.dumps({'sha256':{str(p.relative_to(ref)):hashlib.sha256(b'x').hexdigest() for p in ref.rglob('input')}}))
            smoke.verify_tree(ref,installed)
            f=installed/'brave/input'
            f.chmod(0o755)
            with self.assertRaises(ValueError): smoke.verify_tree(ref,installed)
            f.chmod(0o644);f.write_text('y')
            with self.assertRaises(ValueError): smoke.verify_tree(ref,installed)
            f.unlink()
            with self.assertRaises(ValueError): smoke.verify_tree(ref,installed)
            f.symlink_to(ref/'brave/input')
            with self.assertRaises(ValueError): smoke.verify_tree(ref,installed)
            f.unlink();f.write_bytes(b'x');(installed/'brave/extra').touch()
            with self.assertRaises(ValueError): smoke.verify_tree(ref,installed)
