"""Execute exact transformed lifecycle methods against a host C++ collaborator.
Not a Chromium compile or GPU/device test.
"""
import importlib.util, pathlib, re, shutil, subprocess, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/'.circleci/scripts'/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class Lifetime(unittest.TestCase):
 def source(self):
  source=(ROOT/'tests/fixtures/ordinary-transition/blur_transition_animation_manager.cc').read_text()
  return load('sandium-native-blur-source').implementation(load('apply-sandium-page-transition-full').transform_transition_cc(source))
 def test_ownership_is_retained_until_exit(self):
  s=self.source();timer=s.split('void BlurTransitionAnimationManager::OnBlurHoldTimerExpired() {')[1].split('\n}')[0]
  self.assertNotIn('ResetNavigationState',timer)
  self.assertIn('kFadeToFallbackColor',timer)
  self.assertIn('GetPrimaryMainFrame()->GetGlobalId() != target_rfh_id_',s)
 @unittest.skipUnless(shutil.which('g++'),'g++ unavailable')
 def test_actual_lifecycle_methods(self):
  s=self.source();methods=[]
  for name in ['DidFinishNavigation','DidFirstVisuallyNonEmptyPaint','OnBlurHoldTimerExpired']:
   start=s.index('void BlurTransitionAnimationManager::'+name+'(');end=s.index('\n}\n',start)+2;methods.append(s[start:end])
  harness=r'''
#include <cassert>
struct NavigationHandle {int id;bool committed;int GetNavigationId(){return id;} bool HasCommitted(){return committed;}};
struct Frame {int id=7; int GetGlobalId(){return id;}};
struct Contents {Frame frame;Frame* GetPrimaryMainFrame(){return &frame;}};
enum class TransitionExitReason{kNavigationInterrupted,kFinished};
struct BlurTransitionAnimationManager {
 enum class AnimationState{kBlurShown,kFadeToFallbackColor,kFadeOut};
 int navigation_id_=42,target_rfh_id_=7,exits=0,requests=0;
 bool blur_layer_=true,fallback_color_layer_=true,input_suppressed=true;
 AnimationState animation_state_=AnimationState::kBlurShown;Contents wc;
 Contents* web_contents(){return &wc;}
 void SetAnimationState(AnimationState s){animation_state_=s;}
 void RequestAnimate(){++requests;}
 void StartFadeOut(){animation_state_=AnimationState::kFadeOut;}
 void SignalExit(TransitionExitReason,bool){++exits;navigation_id_=0;target_rfh_id_=0;StartFadeOut();}
 void DidFinishNavigation(NavigationHandle*);
 void DidFirstVisuallyNonEmptyPaint();void OnBlurHoldTimerExpired();
};
'''
  main=r'''
int main(){
 BlurTransitionAnimationManager a;a.OnBlurHoldTimerExpired();
 assert(a.navigation_id_==42 && a.target_rfh_id_==7 && a.requests==1);
 NavigationHandle committed{42,true};a.DidFinishNavigation(&committed);assert(a.exits==0);
 NavigationHandle unrelated{43,false};a.DidFinishNavigation(&unrelated);assert(a.exits==0);
 NavigationHandle abort{42,false};a.DidFinishNavigation(&abort);assert(a.exits==1 && a.navigation_id_==0);
 a.DidFirstVisuallyNonEmptyPaint();assert(a.exits==1);
 BlurTransitionAnimationManager b;b.OnBlurHoldTimerExpired();b.wc.frame.id=8;
 b.DidFirstVisuallyNonEmptyPaint();assert(b.exits==0);
 b.wc.frame.id=7;b.DidFirstVisuallyNonEmptyPaint();assert(b.exits==1);
 BlurTransitionAnimationManager c;c.DidFirstVisuallyNonEmptyPaint();assert(c.exits==1);
 BlurTransitionAnimationManager d;d.OnBlurHoldTimerExpired();
 // DestroyLayer/detach collaborator: layers removed, timer stopped upstream.
 d.blur_layer_=false;d.fallback_color_layer_=false;
 d.DidFirstVisuallyNonEmptyPaint();assert(d.exits==0);
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);(p/'test.cc').write_text(harness+'\n'.join(methods)+main)
   subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror',str(p/'test.cc'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
