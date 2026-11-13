import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.circleci/bridge'))
from quiescence import ensure_quiescent,inspect_writers
spec=importlib.util.spec_from_file_location('legacy_quiescence',ROOT/'.circleci/scripts/sandium-checkpoint-shards.py')
legacy=importlib.util.module_from_spec(spec);sys.modules[spec.name]=legacy;spec.loader.exec_module(legacy)


class Quiescence(unittest.TestCase):
    def start(self,path,args,code,ready):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(code)
        proc=subprocess.Popen([sys.executable,str(path)]+args)
        self.addCleanup(lambda: self.stop(proc))
        limit=time.monotonic()+3
        while not ready.exists() and time.monotonic()<limit:
            if proc.poll() is not None:self.fail('Fixture exited early')
            time.sleep(.01)
        self.assertTrue(ready.exists());return proc
    def stop(self,proc):
        if proc.poll() is None:proc.terminate();proc.wait(timeout=3)

    def test_known_workspace_idle_server_graceful_shutdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();ready=root/'ready';log=work/'buildserver.log'
            code=f"import signal,time;from pathlib import Path\nf=open({str(log)!r},'a');f.write('start\\n');f.flush()\ndef stop(*args):\n f.write('flushed\\n');f.close();raise SystemExit(0)\nsignal.signal(signal.SIGTERM,stop)\nPath({str(ready)!r}).touch()\nwhile True:time.sleep(1)\n"
            proc=self.start(work/'src/build/android/fast_local_dev_server.py',['--exit-on-idle'],code,ready)
            ensure_quiescent(work,legacy,settle_seconds=.2);proc.wait(timeout=2)
            self.assertIn('flushed',log.read_text());self.assertEqual(proc.returncode,0)

    def test_unknown_live_writer_blocks_and_is_not_killed_or_leaks_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();ready=root/'ready';secret='fixture-secret-not-to-log'
            code=f"import time;from pathlib import Path\nf=open({str(work/'live')!r},'w');Path({str(ready)!r}).touch();time.sleep(20)\n"
            proc=self.start(root/'unknown.py',[secret],code,ready);out=io.StringIO()
            with contextlib.redirect_stdout(out):
                with self.assertRaisesRegex(ValueError,'Live workspace writers'):ensure_quiescent(work,legacy,settle_seconds=.05)
            self.assertIsNone(proc.poll());self.assertNotIn(secret,out.getvalue());self.assertIn('"path": "live"',out.getvalue())

    def test_readonly_and_other_workspace_server_not_stopped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();other=root/'other';other.mkdir();ready=root/'ready';(work/'read').write_text('x')
            code=f"import time;from pathlib import Path\nf=open({str(work/'read')!r},'r');g=open({str(other/'log')!r},'w');Path({str(ready)!r}).touch();time.sleep(20)\n"
            proc=self.start(other/'src/build/android/fast_local_dev_server.py',['--exit-on-idle'],code,ready)
            ensure_quiescent(work,legacy,settle_seconds=.05);self.assertIsNone(proc.poll())

    def test_unlinked_fd_is_not_tree_writer_but_does_not_hide_live_fd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();ready=root/'ready'
            code=f"import os,time;from pathlib import Path\nf=open({str(work/'gone')!r},'w');os.unlink({str(work/'gone')!r});g=open({str(work/'live')!r},'w');Path({str(ready)!r}).touch();time.sleep(20)\n"
            proc=self.start(root/'unknown.py',[],code,ready);live,unlinked=inspect_writers(work)
            self.assertTrue(any(x['pid']==proc.pid and x['path']=='gone' for x in unlinked))
            self.assertTrue(any(x['pid']==proc.pid and x['path']=='live' for x in live))
            with self.assertRaisesRegex(ValueError,'Live workspace writers'):ensure_quiescent(work,legacy,settle_seconds=.05)
            self.assertIsNone(proc.poll())

    def test_deleted_name_with_live_hardlink_still_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();ready=root/'ready'
            code=f"import os,time;from pathlib import Path\nf=open({str(work/'gone')!r},'w');os.link({str(work/'gone')!r},{str(work/'kept')!r});os.unlink({str(work/'gone')!r});Path({str(ready)!r}).touch();time.sleep(20)\n"
            proc=self.start(root/'linked.py',[],code,ready);live,unlinked=inspect_writers(work)
            self.assertTrue(any(x['pid']==proc.pid and x['links']==1 for x in live))
            self.assertFalse(any(x['pid']==proc.pid for x in unlinked))
            with self.assertRaisesRegex(ValueError,'Live workspace writers'):ensure_quiescent(work,legacy,settle_seconds=.05)
            self.assertIsNone(proc.poll())

    def test_known_server_without_exit_on_idle_is_not_terminated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();ready=root/'ready'
            code=f"import time;from pathlib import Path\nf=open({str(work/'log')!r},'w');Path({str(ready)!r}).touch();time.sleep(20)\n"
            proc=self.start(work/'src/build/android/fast_local_dev_server.py',[],code,ready)
            with self.assertRaisesRegex(ValueError,'Live workspace writers'):ensure_quiescent(work,legacy,settle_seconds=.05)
            self.assertIsNone(proc.poll())

    def test_unlinked_only_and_naturally_closing_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();ready=root/'ready'
            code=f"import os,time;from pathlib import Path\nf=open({str(work/'gone')!r},'w');os.unlink({str(work/'gone')!r});Path({str(ready)!r}).touch();time.sleep(20)\n"
            proc=self.start(root/'unlinked.py',[],code,ready);ensure_quiescent(work,legacy,settle_seconds=.05);self.assertIsNone(proc.poll());self.stop(proc)
            ready.unlink();code=f"import time;from pathlib import Path\nf=open({str(work/'closing')!r},'w');Path({str(ready)!r}).touch();time.sleep(.15);f.close();time.sleep(20)\n"
            proc=self.start(root/'closing.py',[],code,ready);ensure_quiescent(work,legacy,settle_seconds=1);self.assertIsNone(proc.poll())

if __name__=='__main__':unittest.main()
