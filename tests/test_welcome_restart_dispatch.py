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
 static final int TEXT=0, START_TRACK=1, START_PROGRESS=2;
 Object mPollRunnable=new Object();
 static class Handler { Runnable pending; void removeCallbacks(Object r) {} void postDelayed(Runnable r,long ms){if(ms!=1000)throw new AssertionError();pending=r;} void fire(){pending.run();} }
 static class View { static int VISIBLE=0; }
 static class Switch { void setEnabled(boolean b){} }
 java.util.List<Switch> mSwitches=new java.util.ArrayList<>();
 static class LinearInterpolator {}
 static class ValueAnimator { static boolean enabled=true; static boolean areAnimatorsEnabled(){return enabled;} static ValueAnimator ofInt(int a,int b){if(a!=0||b!=10000)throw new AssertionError("fill range");return new ValueAnimator();} void setDuration(int d){} void setInterpolator(Object o){} java.util.function.Consumer<ValueAnimator> callback; int level; void addUpdateListener(java.util.function.Consumer<ValueAnimator> c){callback=c;} void start(){level=5000;callback.accept(this);level=10000;callback.accept(this);} Object getAnimatedValue(){return level;} }
 ValueAnimator mRestartAnimator;
 static class Drawable {}
 static class ClipDrawable extends Drawable { static int HORIZONTAL=1; int level; ClipDrawable(Drawable d,int g,int o){} void setLevel(int n){level=n;} }
 static class LayerDrawable extends Drawable { LayerDrawable(Drawable[] d){} }
 static class Gravity { static int LEFT=3; }
 Drawable roundRect(int c,int r){return new Drawable();}
 ClipDrawable mRestartButtonFill;
 static class Button { void setEnabled(boolean b) {} void setText(String s) {} void setTextColor(int c) {} void setBackgroundTintList(Object o){} void setBackground(Drawable d){} void setContentDescription(String s){} }
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
  h.startBrowsingWithFeedback();h.startBrowsingWithFeedback();check(prepared==0&&restarted==0&&h.mRestartButtonFill.level==10000);h.mHandler.fire();check(prepared==1&&restarted==1&&started==0);
  reset();h=new RestartHarness();h.mCanStartBrowsing=true;h.mRequiresRestart=true;ValueAnimator.enabled=false;h.startBrowsingWithFeedback();check(h.mRestartButtonFill.level==10000);h.mHandler.fire();check(restarted==1);
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
