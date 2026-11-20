"""Actual recorder: blocked IO, bounded queue, epoch transitions and crash-prefix recovery."""
import json,pathlib,subprocess,tempfile,unittest,struct
ROOT=pathlib.Path(__file__).resolve().parents[1]
JAVA=ROOT/'java/org/chromium/chrome/browser/sandium/diagnostics/SandiumNavigationDiagnostics.java'
HARNESS=r'''import java.io.*;import java.lang.reflect.*;import java.util.concurrent.*;
import org.chromium.chrome.browser.sandium.diagnostics.SandiumNavigationDiagnostics;
public class AsyncHarness {
static Class<?> R=SandiumNavigationDiagnostics.class;
static void hook(Runnable r)throws Exception {Field f=R.getDeclaredField("beforeJournalWriteForTesting");f.setAccessible(true);f.set(null,r);}
static long[] status()throws Exception{Field f=R.getDeclaredField("JOURNAL");f.setAccessible(true);Object w=f.get(null);Method m=w.getClass().getDeclaredMethod("status");m.setAccessible(true);return (long[])m.invoke(w);}
static void drain()throws Exception{long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(10);while(status()[0]!=0){if(System.nanoTime()>end)throw new AssertionError("writer stuck");Thread.sleep(2);}Thread.sleep(10);}
static void row(long id){SandiumNavigationDiagnostics.record(SandiumNavigationDiagnostics.Event.NAV_REDIRECT,id,false,1,0);}
public static void main(String[] a)throws Exception {
File dir=new File(a[1]);SandiumNavigationDiagnostics.initialize(dir);
switch(a[0]){
case "blocked":case "overflow":case "batch":{
 CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
 java.util.concurrent.atomic.AtomicInteger batches=new java.util.concurrent.atomic.AtomicInteger();
 hook(()->{batches.incrementAndGet();if(!Thread.currentThread().getName().equals("SandiumDiagnosticJournal"))throw new AssertionError("IO on caller");entered.countDown();try{release.await();}catch(InterruptedException e){throw new RuntimeException(e);}});
 java.util.concurrent.atomic.AtomicBoolean armed=new java.util.concurrent.atomic.AtomicBoolean();
 SandiumNavigationDiagnostics.start(armed::set);if(!entered.await(5,TimeUnit.SECONDS))throw new AssertionError("no worker");
 if(a[0].equals("blocked")){
  for(int i=0;i<100;i++)row(987654321L+i);
  SandiumNavigationDiagnostics.record(SandiumNavigationDiagnostics.Event.NAV_REDIRECT,123456789L,true,1,0);
  SandiumNavigationDiagnostics.stop();System.out.println(SandiumNavigationDiagnostics.snapshotJson());
  SandiumNavigationDiagnostics.clear();if(!SandiumNavigationDiagnostics.snapshotJson().contains("clearing"))throw new AssertionError("premature clear");
  SandiumNavigationDiagnostics.start();row(42);SandiumNavigationDiagnostics.stop();
 }else if(a[0].equals("batch")){for(int i=0;i<100;i++)row(i+1);SandiumNavigationDiagnostics.stop();
 }else{for(int i=0;i<6000;i++)row(i+1);System.out.println(SandiumNavigationDiagnostics.snapshotJson());if(status()[1]>262144)throw new AssertionError("unbounded queue");}
 if(armed.get())throw new AssertionError("recording gate still armed");
 release.countDown();drain();hook(null);if(a[0].equals("batch")&&batches.get()>5)throw new AssertionError("not batching");break;
}
case "write":SandiumNavigationDiagnostics.start();row(987654321);SandiumNavigationDiagnostics.record(SandiumNavigationDiagnostics.Event.NAV_REDIRECT,123456789,true,1,0);drain();System.out.println("READY");System.out.flush();Thread.sleep(60000);break;
case "stopped":SandiumNavigationDiagnostics.start();row(99);SandiumNavigationDiagnostics.stop();drain();break;
case "clear":SandiumNavigationDiagnostics.clear();drain();break;
case "ioerror":
 if(!dir.delete()||!dir.createNewFile())throw new AssertionError("fault setup");
 java.util.concurrent.atomic.AtomicBoolean failureGate=new java.util.concurrent.atomic.AtomicBoolean();
 SandiumNavigationDiagnostics.start(failureGate::set);row(1);drain();
 if(failureGate.get())throw new AssertionError("write failure kept gate armed");
 if(!SandiumNavigationDiagnostics.storageStatus().equals("storage_error"))throw new AssertionError("missing IO failure");break;
case "read":drain();break;
}
System.out.println(SandiumNavigationDiagnostics.snapshotJson());
}}
'''
class AsyncJournal(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.classes=pathlib.Path(cls.tmp.name);p=cls.classes/'AsyncHarness.java';p.write_text(HARNESS)
  c=subprocess.run(['java','-jar','/tmp/sandium-ecj.jar','-21','-d',str(cls.classes),str(JAVA),str(p)],capture_output=True,text=True)
  if c.returncode:raise AssertionError(c.stdout+c.stderr)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def runjava(self,action,d):
  x=subprocess.run(['java','-cp',str(self.classes),'AsyncHarness',action,str(d)],capture_output=True,text=True,timeout=20);self.assertEqual(x.returncode,0,x.stderr)
  return [json.loads(l) for l in x.stdout.splitlines() if l.startswith('{')]
 def kill_writer(self,d):
  p=subprocess.Popen(['java','-cp',str(self.classes),'AsyncHarness','write',str(d)],stdout=subprocess.PIPE,text=True)
  self.assertEqual(p.stdout.readline().strip(),'READY');p.kill();p.wait();p.stdout.close()
 def test_blocked_io_does_not_block_snapshot_stop_or_epoch_clear(self):
  with tempfile.TemporaryDirectory() as d:
   before,after=self.runjava('blocked',d);self.assertEqual(len(before['events']),100);self.assertGreater(before['journal_pending_commands'],0)
   self.assertEqual(len(after['events']),1);self.assertEqual(after['end'],'user_stopped');self.assertEqual(after['journal_pending_commands'],0)
   recovered=self.runjava('read',d)[-1];self.assertEqual(len(recovered['events']),1);self.assertEqual(recovered['end'],'user_stopped')
   raw=(pathlib.Path(d)/'events.bin').read_bytes();self.assertNotIn(struct.pack('>q',987654321),raw);self.assertNotIn(struct.pack('>q',123456789),raw)
 def test_worker_batches_crc_records_without_reordering(self):
  with tempfile.TemporaryDirectory() as d:
   j=self.runjava('batch',d)[-1];self.assertEqual(len(j['events']),100)
   r=self.runjava('read',d)[-1];self.assertEqual([e['nav'] for e in r['events']],list(range(1,101)));self.assertEqual(r['end'],'user_stopped')
 def test_overflow_is_bounded_and_reported_not_silent(self):
  with tempfile.TemporaryDirectory() as d:
   before,after=self.runjava('overflow',d);self.assertEqual(before['end'],'persistence_queue_full');self.assertEqual(before['journal_rejected_records'],1)
   self.assertLessEqual(before['journal_pending_bytes'],262144);self.assertGreater(len(before['events']),0);self.assertLess(len(before['events']),5000)
   self.assertEqual(len(before['events']),len(after['events']))
 def test_kill_recovers_prefix_without_silent_resume(self):
  with tempfile.TemporaryDirectory() as d:
   self.kill_writer(d);j=self.runjava('read',d)[-1];self.assertEqual(len(j['events']),1);self.assertEqual(j['end'],'recovered_async_prefix');self.assertTrue(j['recovered_async_tail_unknown'])
 def test_crc_tail_and_async_clear(self):
  with tempfile.TemporaryDirectory() as d:
   self.runjava('stopped',d)
   with open(pathlib.Path(d)/'events.bin','ab') as f:f.write(b'\x00\x00\x00\x10broken')
   j=self.runjava('read',d)[-1];self.assertEqual(len(j['events']),1);self.assertEqual(j['end'],'recovered_partial');self.assertEqual(j['recovered_discarded_tails'],1)
   (pathlib.Path(d)/'events.tmp').write_bytes(b'orphan header')
   j=self.runjava('clear',d)[-1];self.assertFalse((pathlib.Path(d)/'events.tmp').exists());self.assertEqual(j['events'],[]);self.assertEqual(j['end'],'cleared');self.assertFalse((pathlib.Path(d)/'events.bin').exists())
 def test_ui_describes_async_recovery_and_clear_truthfully(self):
  ui=(ROOT.parents[1]/'.circleci/features/navigation-diagnostics/ui/SandiumDiagnosticsPreferences.java').read_text()
  self.assertNotIn('Saved sessions can resume',ui)
  self.assertIn('Interrupted sessions do not resume automatically',ui)
  self.assertIn('without waiting for disk writes',ui)
  self.assertIn('check status until cleared',ui)
 def test_io_failure_stops_recording_and_drains(self):
  with tempfile.TemporaryDirectory() as parent:
   d=pathlib.Path(parent)/'journal';j=self.runjava('ioerror',d)[-1];self.assertEqual(j['storage'],'storage_error');self.assertEqual(j['end'],'storage_error');self.assertEqual(j['journal_pending_commands'],0)
if __name__=='__main__':unittest.main()
