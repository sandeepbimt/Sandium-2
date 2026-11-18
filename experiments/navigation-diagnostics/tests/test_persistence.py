import pathlib,subprocess,tempfile,unittest,json,struct,os,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
JAVA=ROOT/'java/org/chromium/chrome/browser/sandium/diagnostics/SandiumNavigationDiagnostics.java'
class Persistence(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.classes=pathlib.Path(cls.tmp.name)
  main=cls.classes/'Harness.java';main.write_text('''import java.io.*;import java.lang.reflect.*;import org.chromium.chrome.browser.sandium.diagnostics.SandiumNavigationDiagnostics;
public class Harness{
static void drain()throws Exception{Field f=SandiumNavigationDiagnostics.class.getDeclaredField("JOURNAL");f.setAccessible(true);Object q=f.get(null);Method m=q.getClass().getDeclaredMethod("status");m.setAccessible(true);long until=System.nanoTime()+10000000000L;while(((long[])m.invoke(q))[0]!=0){if(System.nanoTime()>until)throw new AssertionError("journal stuck");Thread.sleep(2);}Thread.sleep(10);}
public static void main(String[] a)throws Exception{
SandiumNavigationDiagnostics.initialize(new File(a[1]));
switch(a[0]){
case "write":SandiumNavigationDiagnostics.start();SandiumNavigationDiagnostics.record(SandiumNavigationDiagnostics.Event.NAV_REDIRECT,987654321,false,1,0);SandiumNavigationDiagnostics.record(SandiumNavigationDiagnostics.Event.NAV_REDIRECT,555,true,1,0);drain();System.out.println("READY");System.out.flush();Thread.sleep(60000);break;
case "fill":SandiumNavigationDiagnostics.start();SandiumNavigationDiagnostics.record(SandiumNavigationDiagnostics.Event.AD_REQUEST_OMITTED,0,false,1);for(int i=0;i<6000;i++){SandiumNavigationDiagnostics.record(SandiumNavigationDiagnostics.Event.AD_WARNING_MARK,0,false);if(i%100==0)drain();}break;
case "omitted":SandiumNavigationDiagnostics.record(SandiumNavigationDiagnostics.Event.AD_REQUEST_OMITTED,0,false,1);break;
case "resume":SandiumNavigationDiagnostics.record(SandiumNavigationDiagnostics.Event.NAV_REDIRECT,987654321,false,0,1);break;
case "stop":SandiumNavigationDiagnostics.stop();break;
case "clear":SandiumNavigationDiagnostics.clear();break;
case "new":SandiumNavigationDiagnostics.start();break;
}
drain();System.out.println(SandiumNavigationDiagnostics.snapshotJson());}}''')
  subprocess.run(['java','-jar','/tmp/sandium-ecj.jar','-21','-d',str(cls.classes),str(JAVA),str(main)],check=True,capture_output=True)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def runjava(self,action,d):
  return json.loads(subprocess.check_output(['java','-cp',str(self.classes),'Harness',action,str(d)],text=True).splitlines()[-1])
 def kill_writer(self,d):
  p=subprocess.Popen(['java','-cp',str(self.classes),'Harness','write',str(d)],stdout=subprocess.PIPE,text=True);self.assertEqual(p.stdout.readline().strip(),'READY');p.kill();p.wait();p.stdout.close()
 def test_separate_process_kill_preserves_prefix_private_ids_without_resume(self):
  with tempfile.TemporaryDirectory() as d:
   self.kill_writer(d);raw=(pathlib.Path(d)/'events.bin').read_bytes();self.assertNotIn(struct.pack('>q',987654321),raw)
   j=self.runjava('resume',d);self.assertEqual(len(j['events']),1);self.assertEqual(j['events'][0]['nav'],1);self.assertEqual(j['end'],'recovered_async_prefix');self.assertTrue(j['recovered_async_tail_unknown'])
   self.runjava('stop',d);j=self.runjava('resume',d);self.assertEqual(len(j['events']),1)
   self.runjava('clear',d);self.assertFalse((pathlib.Path(d)/'events.bin').exists());self.assertEqual(self.runjava('read',d)['events'],[])
 def test_corrupt_tail_retains_valid_prefix(self):
  with tempfile.TemporaryDirectory() as d:
   self.kill_writer(d)
   with open(pathlib.Path(d)/'events.bin','ab') as f:f.write(b'\x00\x00\x00\x10broken')
   j=self.runjava('resume',d);self.assertEqual(len(j['events']),1);self.assertEqual(j['recovered_discarded_tails'],1);self.assertEqual(j['storage'],'recovered_valid_prefix');self.assertEqual(j['end'],'recovered_partial');j=self.runjava('new',d);self.assertEqual(j['events'],[])
 def test_expired_and_clock_rollback(self):
  for delta in (-121000,10000):
   with tempfile.TemporaryDirectory() as d:
    self.kill_writer(d);p=pathlib.Path(d)/'events.bin';data=bytearray(p.read_bytes());data[4:12]=struct.pack('>q',int(time.time()*1000)+delta);p.write_bytes(data)
    j=self.runjava('resume',d);self.assertEqual(len(j['events']),1);self.assertEqual(j['end'],'restart_time_limit_or_clock_change')
 def test_total_cap_and_omitted_across_restart(self):
  with tempfile.TemporaryDirectory() as d:
   self.kill_writer(d);self.runjava('omitted',d);j=self.runjava('fill',d);self.assertEqual(len(j['events']),5000);self.assertEqual(j['end'],'event_limit');self.assertEqual(j['ad_requests_omitted'],1);j=self.runjava('resume',d);self.assertEqual(len(j['events']),5000);self.assertEqual(j['end'],'event_limit')
 def test_build_or_schema_mismatch_never_relabels_old_rows(self):
  for corrupt_revision in (True,False):
   with tempfile.TemporaryDirectory() as d:
    self.kill_writer(d);p=pathlib.Path(d)/'events.bin';data=bytearray(p.read_bytes())
    if corrupt_revision:
     size=struct.unpack('>H',data[24:26])[0];self.assertGreater(size,0);data[26]=ord('X')
    else:data[20:24]=struct.pack('>i',999)
    p.write_bytes(data)
    j=self.runjava('resume',d);self.assertEqual(j['events'],[]);self.assertEqual(j['end'],'incompatible_recording');self.assertEqual(j['storage'],'incompatible_recording')
    self.assertTrue(p.exists())
    cleared=self.runjava('clear',d);self.assertFalse(p.exists());self.assertEqual(cleared['storage'],'available')
    j=self.runjava('new',d);self.assertEqual(j['end'],'recording')
 def test_storage_error(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'notdir';p.write_text('x');j=self.runjava('new',p);self.assertEqual(j['end'],'storage_error');self.assertEqual(j['storage'],'storage_error')
if __name__=='__main__':unittest.main()
