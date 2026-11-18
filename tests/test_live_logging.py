import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from ci_remote import StreamRedactor,run_logged

class LiveLoggingTests(unittest.TestCase):
    def test_split_secrets(self):
        secret='abcdefghijk'
        for split in range(len(secret)+1):
            redactor=StreamRedactor({'BUILDBUDDY_API_KEY':secret})
            result=redactor.feed('before '+secret[:split])+redactor.feed(secret[split:]+' after',final=True)
            self.assertEqual(result,'before [REDACTED] after')
    def run_command(self,command,check=False,env=None):
        with tempfile.TemporaryDirectory() as d,contextlib.redirect_stdout(io.StringIO()) as console:
            log=Path(d)/'run.log'
            result=run_logged(command,log,phase='test',check=check,env=env,heartbeat_seconds=.03)
            self.assertEqual(log.read_text(),console.getvalue())
            return result,log.read_text()
    def test_stream_stderr_heartbeat_and_redact(self):
        env=dict(os.environ,BUILDBUDDY_API_KEY='sentinel-secret-value')
        code="import os,sys,time;print('before',flush=True);time.sleep(.1);print(os.environ['BUILDBUDDY_API_KEY'],flush=True);print('stderr',file=sys.stderr)"
        result,output=self.run_command([sys.executable,'-u','-c',code],env=env)
        self.assertEqual(result.returncode,0)
        self.assertIn('before',output);self.assertIn('stderr',output)
        self.assertIn('RAWS_PHASE_HEARTBEAT',output)
        self.assertIn('RAWS_PHASE_COMPLETE phase=test exit=0',output)
        self.assertNotIn(env['BUILDBUDDY_API_KEY'],output)
        self.assertIn('[REDACTED]',output)
    def test_return_code_preserved(self):
        result,_=self.run_command([sys.executable,'-c','raise SystemExit(7)'])
        self.assertEqual(result.returncode,7)
        with self.assertRaises(subprocess.CalledProcessError) as e:
            self.run_command([sys.executable,'-c','raise SystemExit(7)'],True)
        self.assertEqual(e.exception.returncode,7)
    def test_timeout_preserved(self):
        result,output=self.run_command(['timeout','--signal=INT','--kill-after=1s','.1s',sys.executable,'-c','import time;time.sleep(3)'])
        self.assertEqual(result.returncode,124)
        self.assertIn('exit=124',output)

if __name__=='__main__':unittest.main()
