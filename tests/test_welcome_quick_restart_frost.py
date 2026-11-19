"""The frozen frost is restricted to the ready Quick Restart state."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
VIEW = ROOT / 'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java'


def extract(source, signature):
    start = source.index(signature)
    pos = source.index('{', start) + 1
    depth = 1
    while depth:
        if source[pos] == '{': depth += 1
        if source[pos] == '}': depth -= 1
        pos += 1
    return source[start:pos]


class Frost(unittest.TestCase):
    def test_actual_ready_and_preparing_state_dispatch(self):
        if not shutil.which('java'): self.skipTest('Java unavailable')
        source = VIEW.read_text()
        methods = '\n'.join(extract(source, signature) for signature in (
            'private void updateStartButtonState()', 'private GradientDrawable quickRestartFrost()'))
        code = """
public class FrostHarness {
 boolean mDestroyed,mRestartInProgress,mCompletionDispatched,mCanStartBrowsing,mStartInvoked,mRequiresRestart;
 static final int PRIMARY_TEXT=10,DISABLED_BUTTON_TEXT=11,START_BUTTON=12,DISABLED_BUTTON=13;
 static class Color {static int rgb(int r,int g,int b){return r*65536+g*256+b;}}
 static class GradientDrawable {
  enum Orientation {TOP_BOTTOM}
  int color,stroke;float radius;int[] colors;
  GradientDrawable(int c){color=c;}
  GradientDrawable(Orientation o,int[] c){colors=c;}
  void setCornerRadius(float n){radius=n;} void setStroke(int n,int c){stroke=c;}
 }
 static class Button {
  boolean enabled;int textColor;GradientDrawable background;String text,description;
  void setEnabled(boolean b){enabled=b;}void setTextColor(int c){textColor=c;}
  void setBackgroundTintList(Object o){}void setBackground(GradientDrawable d){background=d;}
  void setText(String s){text=s;}void setContentDescription(String s){description=s;}
 }
 static class Handler {void removeCallbacks(Object o){}}
 static class Activity {String getString(int id){return "...";}}
 static class R {static class string {static int sandium_welcome_dots=1;}}
 Button mStartButton=new Button();Handler mHandler=new Handler();Activity mActivity=new Activity();
 Object mDotsRunnable=new Object();int dots;
 void updatePreparingDots(){dots++;}
 String readyButtonLabel(){return mRequiresRestart?"Quick Restart":"Start browsing";}
 int dp(int n){return n;}
 GradientDrawable roundRect(int c,int r){return new GradientDrawable(c);}
 """ + methods + """
 static void check(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[] a){
  FrostHarness h=new FrostHarness();
  h.mRequiresRestart=true;h.updateStartButtonState();
  check(!h.mStartButton.enabled&&h.mStartButton.background.color==DISABLED_BUTTON&&h.dots==1);
  h.mCanStartBrowsing=true;h.updateStartButtonState();
  check(h.mStartButton.enabled&&h.mStartButton.text.equals("Quick Restart"));
  check(h.mStartButton.background.colors.length==2&&h.mStartButton.background.radius==28);
  check(h.mStartButton.textColor==Color.rgb(243,242,239));
  h.mRequiresRestart=false;h.updateStartButtonState();
  check(h.mStartButton.background.color==START_BUTTON&&h.mStartButton.textColor==PRIMARY_TEXT);
  check(h.mStartButton.text.equals("Start browsing"));
  h.mRestartInProgress=true;h.mRequiresRestart=true;h.updateStartButtonState();
  check(h.mStartButton.background.color==START_BUTTON);
 }
}
"""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'FrostHarness.java'; p.write_text(code)
            compiler = ['javac'] if shutil.which('javac') else ['java', '--module', 'jdk.compiler/com.sun.tools.javac.Main']
            result = subprocess.run(compiler + [str(p)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run(['java', '-cp', td, 'FrostHarness'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_original_geometry_and_pressed_palette(self):
        source = VIEW.read_text()
        self.assertIn('ViewGroup.LayoutParams.MATCH_PARENT, dp(52)', source)
        self.assertIn('mStartButton.setMinHeight(dp(52))', source)
        pressed = extract(source, 'private void startBrowsingWithFeedback()')
        self.assertNotIn('quickRestartFrost', pressed)
        self.assertIn('roundRect(START_TRACK, 28)', pressed)
        self.assertIn('roundRect(START_PROGRESS, 28)', pressed)
        self.assertIn('mStartButton.setTextColor(PRIMARY_TEXT)', pressed)


if __name__ == '__main__': unittest.main()
