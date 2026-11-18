import hashlib,io,subprocess,sys,tarfile,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from final_archive_proof import verify_archived_apk,APK_MEMBER
class FinalArchiveProofTests(unittest.TestCase):
 def test_real_tar_zstd_member_readback(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);data=b'verified APK fixture';p=r/'a.tar'
   with tarfile.open(p,'w') as t:
    i=tarfile.TarInfo(APK_MEMBER);i.size=len(data);t.addfile(i,io.BytesIO(data))
   subprocess.run(['zstd','-q',str(p),'-o',str(r/'a.tar.zst')],check=True)
   m={'shards':[{'name':'a.tar.zst','root_paths':['work/source/src/out/RawSandium']}]}
   proof=verify_archived_apk(m,r,hashlib.sha256(data).hexdigest(),10);self.assertEqual(proof['bytes'],len(data))
   with self.assertRaisesRegex(ValueError,'digest'):verify_archived_apk(m,r,'wrong',10)
 def test_missing_member_route(self):
  with self.assertRaisesRegex(ValueError,'exactly one'):verify_archived_apk({'shards':[]},Path('/tmp'),'x',10)
