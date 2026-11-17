"""Destination-policy ordinary fallback: exact transformed C++ decision tests."""
import importlib.util
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('full',ROOT/'.circleci/scripts/apply-sandium-page-transition-full.py')
full=importlib.util.module_from_spec(spec);spec.loader.exec_module(full)
BASE=(ROOT/'tests/fixtures/ordinary-transition/blur_transition_animation_manager.cc').read_text()
def output():return full.transform_transition_cc(BASE)
def decision(s):return s[s.index('  // SANDIUM_DESTINATION_FALLBACK_V1'):s.index('  fallback_color_layer_->SetBackgroundColor(background_color);')]
class DestinationFallback(unittest.TestCase):
 def test_ready_to_commit_final_url_and_no_timing_change(self):
  s=output();d=decision(s)
  ready=s[s.index('void BlurTransitionAnimationManager::ReadyToCommitNavigation('):s.index('void BlurTransitionAnimationManager::RenderFrameHostStateChanged(')]
  self.assertIn(d,ready)
  self.assertIn('web_contents(), navigation_handle->GetURL()',d)
  self.assertNotIn('GetLastCommittedURL',d)
  for name in ['OnBlurHoldTimerExpired','DidFirstVisuallyNonEmptyPaint','DidFinishNavigation']:
   def method(text):
    a=text.index('void BlurTransitionAnimationManager::'+name+'(')
    b=text.find('\nvoid BlurTransitionAnimationManager::',a+1)
    return text[a:b if b!=-1 else len(text)]
   self.assertEqual(method(BASE),method(s))
 def test_legacy_checkpoint_migrates_and_replays(self):
  s=output();d=decision(s)
  old='''  SkColor4f background_color = SkColors::kWhite;
  if (base::FeatureList::IsEnabled(
          blink::features::kForceWebContentsDarkMode)) {
    background_color = SkColors::kBlack;
  } else if (auto theme_color = delegate->GetThemeColor()) {
    background_color = SkColor4f::FromColor(*theme_color);
  }
'''
  self.assertEqual(s,full.transform_transition_cc(s.replace(d,old)))
  self.assertEqual(s,full.transform_transition_cc(s))
 @unittest.skipUnless(shutil.which('g++'),'g++ unavailable')
 def test_exact_selection_matrix(self):
  code=r'''
#include <optional>
#include <cassert>
struct GURL { bool web=true; int identity=42; bool SchemeIsHTTPOrHTTPS()const{return web;} };
struct Origin { bool is_opaque=false; bool opaque()const{return is_opaque;} };
struct Params { bool is_view_source=false; };
struct Handle { GURL url; bool error=false,pdf=false; std::optional<Origin> origin=Origin{}; Params params;
 auto GetOriginToCommit(){return origin;} const GURL& GetURL(){return url;} bool IsErrorPage(){return error;} bool IsPdf(){return pdf;} };
struct NavigationRequest { static NavigationRequest* From(Handle* h){current=h;static NavigationRequest n;return &n;} static inline Handle* current;const Params& commit_params(){return current->params;} };
using SkColor4f=int; namespace SkColors { constexpr int kWhite=0xffffff,kBlack=0; }
'''.replace('using SkColor4f=int;', '''struct SkColor4f { int value; constexpr SkColor4f(int x):value(x){} static SkColor4f FromColor(int x){return x;} };''')+r'''
namespace blink::features {constexpr int kForceWebContentsDarkMode=1;}
namespace base { struct FeatureList { static inline bool enabled=false;static bool IsEnabled(int){return enabled;} }; }
struct Client { int policy=-1,calls=0,seen=0; int GetSandiumDarkPageFlagsForNavigation(void*,const GURL& url){++calls;seen=url.identity;return policy;} } client;
struct Content {Client* browser(){return &client;}} content;
Content* GetContentClient(){return &content;} void* web_contents(){return nullptr;}
struct Delegate {std::optional<int> theme=0xabcdef;int calls=0;auto GetThemeColor(){++calls;return theme;}};
int select(Handle* navigation_handle,Delegate* delegate) {
'''+decision(output())+r'''
return background_color.value;
}
int main(){
 for(int policy: {-1,0,1})for(bool global:{false,true})for(bool theme:{false,true}) {
  Handle h;Delegate d;if(!theme)d.theme.reset();client.policy=policy;client.calls=0;base::FeatureList::enabled=global;
  int result=select(&h,&d);assert(client.calls==1&&client.seen==42);
  assert(result==(policy==1?0:policy==0?0xffffff:global?0:theme?0xabcdef:0xffffff));
  if(policy>=0)assert(d.calls==0);
 }
 // Independent calls model redirected final URL, then a fresh/new-tab target:
 // no retained navigation policy or outgoing theme may leak into explicit OFF.
 {Handle final;Delegate d;final.url.identity=73;client.policy=1;
  assert(select(&final,&d)==0);assert(client.seen==73);
  Handle fresh;fresh.url.identity=99;client.policy=0;base::FeatureList::enabled=true;
  assert(select(&fresh,&d)==0xffffff);assert(client.seen==99);}
 for(int exclusion=0;exclusion<6;++exclusion){
  Handle h;Delegate d;client.policy=1;client.calls=0;base::FeatureList::enabled=false;
  if(exclusion==0)h.url.web=false;if(exclusion==1)h.error=true;if(exclusion==2)h.pdf=true;
  if(exclusion==3)h.params.is_view_source=true;if(exclusion==4)h.origin.reset();if(exclusion==5)h.origin->is_opaque=true;
  assert(select(&h,&d)==0xabcdef);assert(client.calls==0);
 }
}
'''
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'test.cc').write_text(code)
   subprocess.run(['g++','-std=c++20',str(p/'test.cc'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
