"""Execute production dispatch method against small lifecycle collaborators, not Android UI."""
from pathlib import Path
import subprocess, tempfile, unittest, shutil
ROOT=Path(__file__).resolve().parents[1]
class WelcomeRestart(unittest.TestCase):
 def test_dispatch_readiness_once_and_no_cosmetic_timer(self):
  s=(ROOT/'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
  method=s.split('    private void startBrowsingWithFeedback() {',1)[1].split('    private void setProtectionEnabled',1)[0]
  method='    private void startBrowsingWithFeedback() {'+method
  self.assertNotIn('animate()',method); self.assertNotIn('ValueAnimator',method)
  self.assertNotIn('postDelayed',method)
  code='''public class RestartHarness {
 boolean mDestroyed,mCanStartBrowsing,mStartInvoked,mRestartInProgress,mRequiresRestart;
 static int prepared, restarted, started;
 static final int PRIMARY_TEXT=0;
 Object mPollRunnable=new Object();
 static class Handler { void removeCallbacks(Object r) {} }
 static class Button { void setEnabled(boolean b) {} void setText(String s) {} void setTextColor(int c) {} }
 static class Listener { void onStartBrowsing(){started++;} void onPrepareForRestart(){prepared++;} }
 static class BraveRelaunchUtils { static void restart(){if(prepared!=1)throw new AssertionError("prepare order");restarted++;} }
 Handler mHandler=new Handler(); Button mStartButton=new Button(); Listener mListener=new Listener();
 '''+method+'''
 static void reset(){prepared=restarted=started=0;}
 static void check(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[] args) {
  RestartHarness h=new RestartHarness();h.startBrowsingWithFeedback();check(!h.mStartInvoked&&restarted==0);
  h.mCanStartBrowsing=true;h.mDestroyed=true;h.startBrowsingWithFeedback();check(!h.mStartInvoked&&restarted==0);
  h.mDestroyed=false;h.startBrowsingWithFeedback();h.startBrowsingWithFeedback();check(started==1&&prepared==0&&restarted==0);
  reset();h=new RestartHarness();h.mCanStartBrowsing=true;h.mRequiresRestart=true;
  h.startBrowsingWithFeedback();h.startBrowsingWithFeedback();check(prepared==1&&restarted==1&&started==0);
 }
}'''
  if not shutil.which('javac'): self.skipTest('Java compiler unavailable; dispatch harness not executed')
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'RestartHarness.java';p.write_text(code)
   subprocess.run(['javac',str(p)],check=True,capture_output=True)
   subprocess.run(['java','-cp',d,'RestartHarness'],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
