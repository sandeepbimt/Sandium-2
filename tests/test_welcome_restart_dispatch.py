"""Execute production dispatch method against small lifecycle collaborators, not Android UI."""
from pathlib import Path
import subprocess, tempfile, unittest, shutil
ROOT=Path(__file__).resolve().parents[1]
class WelcomeRestart(unittest.TestCase):
 def test_dispatch_readiness_once_after_feedback(self):
  s=(ROOT/'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
  method=s.split('    private void startBrowsingWithFeedback() {',1)[1].split('    private void setProtectionEnabled',1)[0]
  method='    private void startBrowsingWithFeedback() {'+method
  perform='private void performRestart() {'+s.split('    private void performRestart() {',1)[1].split('\n    }',1)[0]+'\n    }'
  self.assertIn('postDelayed(mRestartRunnable, 1000)',method)
  self.assertIn('mHandler.removeCallbacks(mRestartRunnable)',s)
  self.assertIn('mRestartAnimator.cancel()',s)
  code='''public class RestartHarness {
 boolean mDestroyed,mCanStartBrowsing,mStartInvoked,mRestartInProgress,mRequiresRestart;
 static int prepared, restarted, started;
 static final int PRIMARY_TEXT=0;
 Object mPollRunnable=new Object();
 static class Handler { Runnable pending; void removeCallbacks(Object r) {} void postDelayed(Runnable r,long ms){if(ms!=1000)throw new AssertionError();pending=r;} void fire(){pending.run();} }
 static class View { static int VISIBLE=0; }
 static class Switch { void setEnabled(boolean b){} }
 java.util.List<Switch> mSwitches=new java.util.ArrayList<>();
 static class LinearInterpolator {}
 static class ValueAnimator { static boolean enabled=true; static boolean areAnimatorsEnabled(){return enabled;} static ValueAnimator ofInt(int a,int b){return new ValueAnimator();} void setDuration(int d){} void setInterpolator(Object o){} void addUpdateListener(java.util.function.Consumer<ValueAnimator> c){} void start(){} Object getAnimatedValue(){return 1;} }
 ValueAnimator mRestartAnimator;
 static class Progress { void setVisibility(int v){} void setContentDescription(String s){} void setProgress(int n){} }
 Progress mRestartProgress=new Progress();
 static class Button { void setEnabled(boolean b) {} void setText(String s) {} void setTextColor(int c) {} }
 static class Listener { void onStartBrowsing(){started++;} void onPrepareForRestart(){prepared++;} }
 static class BraveRelaunchUtils { static void restart(){if(prepared!=1)throw new AssertionError("prepare order");restarted++;} }
 Handler mHandler=new Handler(); Button mStartButton=new Button(); Listener mListener=new Listener();
 '''+perform+'\nRunnable mRestartRunnable = this::performRestart;\n'+method+'''
 static void reset(){prepared=restarted=started=0;}
 static void check(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[] args) {
  RestartHarness h=new RestartHarness();h.startBrowsingWithFeedback();check(!h.mStartInvoked&&restarted==0);
  h.mCanStartBrowsing=true;h.mDestroyed=true;h.startBrowsingWithFeedback();check(!h.mStartInvoked&&restarted==0);
  h.mDestroyed=false;h.startBrowsingWithFeedback();h.startBrowsingWithFeedback();check(started==1&&prepared==0&&restarted==0);
  reset();h=new RestartHarness();h.mCanStartBrowsing=true;h.mRequiresRestart=true;
  h.startBrowsingWithFeedback();h.startBrowsingWithFeedback();check(prepared==0&&restarted==0);h.mHandler.fire();check(prepared==1&&restarted==1&&started==0);
  reset();h=new RestartHarness();h.mCanStartBrowsing=true;h.mRequiresRestart=true;ValueAnimator.enabled=false;h.startBrowsingWithFeedback();h.mHandler.fire();check(restarted==1);
  reset();h=new RestartHarness();h.mCanStartBrowsing=true;h.mRequiresRestart=true;h.startBrowsingWithFeedback();h.mDestroyed=true;h.mHandler.fire();check(restarted==0&&prepared==0);
 }
}'''
  compiler=['javac'] if shutil.which('javac') else ['java','--module','jdk.compiler/com.sun.tools.javac.Main']
  if not shutil.which('java'): self.skipTest('Java unavailable; dispatch harness not executed')
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'RestartHarness.java';p.write_text(code)
   subprocess.run(compiler+[str(p)],check=True,capture_output=True)
   subprocess.run(['java','-cp',d,'RestartHarness'],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
