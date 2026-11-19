import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('prepaint',ROOT/'experiments/single-handoff/prepaint_background.py')
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)

class PrepaintBackgroundTest(unittest.TestCase):
    def test_exact_source_idempotence_and_drift_rejection(self):
        source=M.fixture(); transformed=M.transform(source)
        self.assertEqual(M.transform(transformed),transformed)
        self.assertEqual(transformed.count(M.INSTALL),1)
        with self.assertRaises(ValueError): M.transform(source+'// unknown\n')
        self.assertNotIn('SetPageBaseBackgroundColor', source)
        self.assertNotIn('PostDelayed', M.HELPER)

    def test_actual_cpp_helper_lifecycle(self):
        # Execute the real emitted helper, not a Python reimplementation. Stubs
        # exercise policy/lifetime logic; they do not prove Android renderer pixels.
        stub=r'''
#include <optional>
#include <cassert>
#define WEB_CONTENTS_USER_DATA_KEY_DECL()
#define WEB_CONTENTS_USER_DATA_KEY_IMPL(T)
constexpr int SK_ColorBLACK=0;
namespace base { enum TerminationStatus { CRASH }; }
struct Url { bool http=true; bool SchemeIsHTTPOrHTTPS()const{return http;} };
namespace content {
enum class Visibility { VISIBLE, HIDDEN, OCCLUDED };
struct WebContents { Visibility visibility=Visibility::VISIBLE; bool dark=true,loading=false;
std::optional<int> color; int writes=0;
Visibility GetVisibility(){return visibility;} bool IsLoading(){return loading;}
void SetPageBaseBackgroundColor(std::optional<int> c){color=c;++writes;} };
struct NavigationHandle { bool primary=true,same=false,commit=true,error=false,cache=false,prerender=false; Url url;
bool IsInPrimaryMainFrame(){return primary;} bool IsSameDocument(){return same;}
bool HasCommitted(){return commit;} bool IsErrorPage(){return error;}
bool IsServedFromBackForwardCache(){return cache;} bool IsPrerenderedPageActivation(){return prerender;}
Url GetURL(){return url;} };
class WebContentsObserver { WebContents* wc; public: explicit WebContentsObserver(WebContents* w):wc(w){}
virtual ~WebContentsObserver()=default; WebContents* web_contents(){return wc;}
virtual void DidStartNavigation(NavigationHandle*){} virtual void DidFinishNavigation(NavigationHandle*){}
virtual void DidFirstVisuallyNonEmptyPaint(){} virtual void DidStopLoading(){}
virtual void OnVisibilityChanged(Visibility){} virtual void PrimaryMainFrameRenderProcessGone(base::TerminationStatus){}
virtual void WebContentsDestroyed(){} };
template<class T> struct WebContentsUserData { explicit WebContentsUserData(WebContents&){} };
}
namespace night_mode { struct WebContentsThemeClient { content::WebContents* wc;
static WebContentsThemeClient* FromWebContents(content::WebContents* w){static WebContentsThemeClient t;t.wc=w;return &t;}
bool IsNightModeEnabled(){return wc->dark;} }; }
'''
        test=r'''
int main(){
content::WebContents wc; content::NavigationHandle nav;
SandiumPrePaintBackground p(&wc);
assert(!wc.color); // do not recolor restored tabs at initialization
p.DidFinishNavigation(&nav); assert(wc.color==SK_ColorBLACK);
p.DidFirstVisuallyNonEmptyPaint(); assert(!wc.color); // light/transparent page canvas restored
int writes=wc.writes;p.DidFirstVisuallyNonEmptyPaint();assert(wc.writes==writes);
p.DidFinishNavigation(&nav);p.DidStartNavigation(&nav);assert(!wc.color);
nav.commit=false;p.DidFinishNavigation(&nav);assert(!wc.color);nav.commit=true;
p.DidFinishNavigation(&nav);
content::NavigationHandle olderCancelled;olderCancelled.commit=false;
p.DidFinishNavigation(&olderCancelled);assert(wc.color==SK_ColorBLACK);
wc.loading=true;p.DidStopLoading();assert(wc.color==SK_ColorBLACK);
wc.loading=false;p.DidStopLoading();assert(!wc.color);
p.DidFinishNavigation(&nav);p.OnVisibilityChanged(content::Visibility::HIDDEN);assert(!wc.color);
p.DidFinishNavigation(&nav);p.PrimaryMainFrameRenderProcessGone(base::CRASH);assert(!wc.color);
for(int kind=0;kind<7;++kind){
nav={};wc.dark=true;wc.visibility=content::Visibility::VISIBLE;
if(kind==0)nav.same=true;if(kind==1)nav.primary=false;if(kind==2)nav.cache=true;
if(kind==3)nav.prerender=true;if(kind==4)nav.error=true;if(kind==5)nav.url.http=false;
if(kind==6)wc.visibility=content::Visibility::HIDDEN;
p.DidFinishNavigation(&nav);assert(!wc.color);
}
nav={};wc.visibility=content::Visibility::VISIBLE;wc.dark=false;
p.DidFinishNavigation(&nav);assert(!wc.color);
wc.dark=true;p.DidFinishNavigation(&nav);assert(wc.color==SK_ColorBLACK);
writes=wc.writes;p.WebContentsDestroyed();assert(wc.writes==writes);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.cc';path.write_text(stub+M.HELPER.replace(' private:', ' public:')+test)
            subprocess.run(['g++','-std=c++20','-Wall','-Wextra',str(path),'-o',tmp+'/test'],check=True,capture_output=True)
            subprocess.run([tmp+'/test'],check=True)

if __name__=='__main__': unittest.main()
