import shutil,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.circleci/full-u'))
import archive as a,protocol as p
class Archive(unittest.TestCase):
 def test_actual_source_only_remote_copy_fresh_restore(self):
  with tempfile.TemporaryDirectory() as t:
   writer=Path(t)/'writer';writer.mkdir();work=p.owned(writer/'brave-work','scope');(work/'partial').write_text('source-acquisition')
   c=a.capture(writer,'scope','source-acquiring','time-slice',1,'a'*40,None)
   with self.assertRaises(p.ProtocolError):p.verify(c,'scope',True)
   fresh=Path(t)/'fresh';fresh.mkdir()
   shutil.copytree(writer/a.native.SHARD_DIR_NAME,fresh/a.native.SHARD_DIR_NAME);shutil.copyfile(writer/a.native.MANIFEST_NAME,fresh/a.native.MANIFEST_NAME)
   a.restore_candidate(fresh,c,'scope',None)
   r=a.accept_after_fresh_restore(c,'scope',fresh,Path(t)/'accepted.json');p.verify(r,'scope',True)
   self.assertEqual((fresh/'brave-work/partial').read_text(),'source-acquisition')
   self.assertFalse((fresh/'brave-work/src/out').exists())
   with self.assertRaises(FileExistsError):a.accept_after_fresh_restore(c,'scope',fresh,Path(t)/'accepted.json')
 def test_failed_compile_preserves_only_verified_source(self):
  with tempfile.TemporaryDirectory() as t:
   writer=Path(t)/'writer';writer.mkdir();work=p.owned(writer/'brave-work','scope')
   (work/'src/out/Bad').mkdir(parents=True);(work/'src/out/Bad/broken.o').write_text('unhealthy')
   (work/'src/source.cc').write_text('valid source')
   c=a.capture(writer,'scope','source-synced','recovered-source',1,'a'*40,lambda phase,w:None,source_only=True)
   fresh=Path(t)/'fresh';fresh.mkdir();shutil.copytree(writer/a.native.SHARD_DIR_NAME,fresh/a.native.SHARD_DIR_NAME);shutil.copyfile(writer/a.native.MANIFEST_NAME,fresh/a.native.MANIFEST_NAME)
   a.restore_candidate(fresh,c,'scope',lambda phase,w:None)
   self.assertFalse((fresh/'brave-work/src/out').exists());self.assertEqual((fresh/'brave-work/src/source.cc').read_text(),'valid source')
   accepted=a.accept_after_fresh_restore(c,'scope',fresh,Path(t)/'receipt')
   self.assertEqual(p.verify(accepted,'scope',True)['outcome'],'recovered-source')
if __name__=='__main__':unittest.main()
