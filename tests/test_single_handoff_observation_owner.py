"""Compile the actual dormant owner and collector with explicit Chromium API doubles."""
import importlib.util, pathlib, re, subprocess, tempfile, unittest, os, gzip, json, hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('snapshot_fixture',ROOT/'tests/test_single_handoff_snapshot.py')
snapshot=importlib.util.module_from_spec(spec);spec.loader.exec_module(snapshot)
BASE=ROOT/'experiments/single-handoff/components'
CC=BASE/'content/browser/android/native_page_handoff_observation_owner.cc'
HH=BASE/'content/public/browser/android/native_page_handoff_observation_owner.h'
METADATA_FIELDS=r"""
float device_scale_factor=1,page_scale_factor=1,external_page_scale_factor=1;
struct Controls {float top_controls_height=0,top_controls_shown_ratio=0,
bottom_controls_height=0,bottom_controls_shown_ratio=0,
top_controls_min_height_offset=0,bottom_controls_min_height_offset=0;
bool has_offset_tag=false;bool operator==(const Controls&)const=default;} browser_controls_metadata;
int root_scroll_offset=0,root_background_color=0,selection=0,tracked_element_rects=0,delegated_ink_metadata=0,new_vertical_scroll_direction=0;
bool is_scroll_offset_at_top=true,root_overflow_y_hidden=false,has_transparent_background=false,is_mobile_optimized=false;
float min_page_scale_factor=0,max_page_scale_factor=0;
gfx::Size scrollable_viewport_size,root_layer_size;
bool operator==(const RenderFrameMetadata&)const=default;
"""
EXTRA=r'''
#include <functional>
#include <memory>
#include <utility>
#include <cassert>
#define CHECK(x) assert(x)
template<class T> using scoped_refptr=std::shared_ptr<T>;
namespace viz {struct FrameTimingDetails {};}
namespace base {
enum TerminationStatus {TERMINATION_STATUS_PROCESS_CRASHED};
template<class> class OnceCallback;
template<class R,class... A> class OnceCallback<R(A...)> {
 std::function<R(A...)> f;
 public:OnceCallback()=default;template<class F> OnceCallback(F x):f(std::move(x)){}
 OnceCallback(OnceCallback&&)=default;OnceCallback& operator=(OnceCallback&&)=default;
 OnceCallback(const OnceCallback&)=delete;OnceCallback& operator=(const OnceCallback&)=delete;
 void Reset(){f=nullptr;} explicit operator bool()const{return bool(f);} R Run(A...a){auto local=std::move(f);f=nullptr;return local(std::forward<A>(a)...);}
};
template<class> class RepeatingCallback;
template<class R,class... A> class RepeatingCallback<R(A...)> {
 std::function<R(A...)> f;
 public:RepeatingCallback()=default;template<class F> RepeatingCallback(F x):f(std::move(x)){}
 explicit operator bool()const{return bool(f);} R Run(A...a){auto local=f;return local(std::forward<A>(a)...);}void Reset(){f=nullptr;}
};
template<class T> class WeakPtr {T* p;std::weak_ptr<int> token;
 public:WeakPtr(T* x,std::weak_ptr<int> t):p(x),token(t){} explicit operator bool()const{return !token.expired();}T* operator->()const{return p;}};
template<class T> class WeakPtrFactory {T* p;std::shared_ptr<int> token=std::make_shared<int>(0);
 public:explicit WeakPtrFactory(T* x):p(x){}WeakPtr<T> GetWeakPtr(){return {p,token};}void InvalidateWeakPtrs(){token=std::make_shared<int>(0);}};
template<class F,class A> auto BindOnce(F f,A a){return [f,a](const viz::FrameTimingDetails& d){f(a,d);};}
}
namespace content {
using RenderFrameHost=RenderFrameHostImpl;
struct Page {};
struct NavigationHandle {bool primary=true;bool IsInPrimaryMainFrame(){return primary;}};
class WebContentsObserver {WebContents* contents;
 public:explicit WebContentsObserver(WebContents* w):contents(w){}virtual ~WebContentsObserver()=default;
 WebContents* web_contents(){return contents;}void Observe(WebContents* w){contents=w;}
 virtual void DidStartNavigation(NavigationHandle*){}virtual void PrimaryPageChanged(Page&){}
 virtual void PrimaryPageWillBeDeactivated(Page&){}virtual void RenderFrameDeleted(RenderFrameHost*){}
 virtual void PrimaryMainFrameRenderProcessGone(base::TerminationStatus){}
 virtual void OnVisibilityChanged(Visibility){}virtual void WebContentsDestroyed(){}
};
class Compositor {
 public:std::vector<base::OnceCallback<void(const viz::FrameTimingDetails&)>> callbacks;
 void RequestSuccessfulPresentationTimeForNextFrame(base::OnceCallback<void(const viz::FrameTimingDetails&)> callback){callbacks.push_back(std::move(callback));}
 void Deliver(size_t n){auto callback=std::move(callbacks[n]);std::move(callback).Run(viz::FrameTimingDetails{});}
};
}
'''
MAIN=r'''
#include "content/public/browser/android/native_page_handoff_observation_owner.h"
using namespace content;
using Owner=NativePageHandoffObservationOwner;
using Reason=Owner::EndReason;
struct Fixture {
 WebContents wc;Compositor compositor;scoped_refptr<cc::slim::Layer> scene=std::make_shared<cc::slim::Layer>();
 std::unique_ptr<Owner> owner;int ended=0;Reason reason=Reason::kCancelled;bool observed=false;
 Fixture(){scene->kids={&wc.frame.widget.view.layer};}
 void Start(){auto target=CaptureNativePageHandoffTarget(wc,1);assert(target);
 owner=std::make_unique<Owner>(wc,*target,[this](){return scene;},[this](Reason r, std::optional<NativePageHandoffSurfaceObservation> o){ended++;reason=r;observed=o.has_value();});}
 void Frame(){owner->ObserveAtFinalization(compositor);}
};
int main(){
 {Fixture f;f.Start();f.Frame();f.Frame();assert(f.compositor.callbacks.size()==1);f.compositor.Deliver(0);assert(f.ended==1&&f.observed&&f.reason==Reason::kPresentationObserved);f.Frame();f.owner.reset();assert(f.ended==1);}
 {Fixture f;f.Start();f.Frame();f.owner->Revoke(Reason::kCancelled);f.compositor.Deliver(0);assert(f.ended==1&&!f.observed);}
 {Fixture f;f.Start();f.Frame();f.owner.reset();f.compositor.Deliver(0);assert(f.ended==0);}
 {Fixture f;f.Start();f.wc.controller.pending=true;f.Frame();assert(f.ended==1&&f.reason==Reason::kNavigationStarted&&f.compositor.callbacks.empty());}
 {Fixture f;f.Start();f.Frame();f.wc.controller.pending=true;f.compositor.Deliver(0);assert(f.ended==1&&!f.observed);}
 {Fixture f;f.Start();f.Frame();auto& m=f.wc.frame.widget.provider.metadata;m.device_scale_factor=2;f.Frame();assert(f.compositor.callbacks.size()==2);f.compositor.Deliver(0);assert(f.ended==0);f.compositor.Deliver(1);assert(f.observed&&f.ended==1);}
 {Fixture f;f.Start();f.Frame();f.wc.frame.widget.provider.metadata.device_scale_factor=2;f.compositor.Deliver(0);assert(f.ended==0);f.Frame();assert(f.compositor.callbacks.size()==2);f.compositor.Deliver(1);assert(f.observed);}
 // Non-geometric hints do not require a new presentation observation or a quiet page.
 {Fixture f;f.Start();f.Frame();auto& m=f.wc.frame.widget.provider.metadata;
  m.selection++;m.tracked_element_rects++;m.delegated_ink_metadata++;m.is_mobile_optimized=true;m.new_vertical_scroll_direction++;
  f.Frame();assert(f.compositor.callbacks.size()==1);f.compositor.Deliver(0);assert(f.observed&&f.ended==1);}
 // Offset-tag authority is not compared by pinned BrowserControlsMetadata::operator==.
 {Fixture f;f.Start();f.Frame();f.wc.frame.widget.provider.metadata.browser_controls_metadata.has_offset_tag=true;
  f.compositor.Deliver(0);assert(f.ended==0);f.Frame();assert(f.compositor.callbacks.size()==2);f.compositor.Deliver(1);assert(f.observed);}
 // Geometry/background changes still require a fresh frame; never mask them as hints.
 for(int field=0;field<4;field++){Fixture f;f.Start();f.Frame();auto& m=f.wc.frame.widget.provider.metadata;
  if(field==0)m.browser_controls_metadata.bottom_controls_shown_ratio=1;
  if(field==1)m.root_scroll_offset=2;
  if(field==2)m.has_transparent_background=true;
  if(field==3)m.root_background_color=3;
  f.compositor.Deliver(0);assert(f.ended==0);f.Frame();f.compositor.Deliver(1);assert(f.observed);}
 {Fixture f;f.Start();f.Frame();f.wc.frame.doc.id++;f.compositor.Deliver(0);assert(f.ended==0&&!f.observed);f.owner->Revoke(Reason::kDeadline);assert(f.ended==1);}
 {Fixture f;f.Start();f.Frame();f.scene=std::make_shared<cc::slim::Layer>();f.scene->kids={&f.wc.frame.widget.view.layer};f.compositor.Deliver(0);assert(f.ended==1&&f.reason==Reason::kSceneChanged);}
 {Fixture f;f.Start();f.Frame();f.scene.reset();f.Frame();f.compositor.Deliver(0);assert(f.ended==0);f.owner->Revoke(Reason::kDeadline);assert(f.ended==1);}
 {Fixture f;f.Start();f.Frame();NavigationHandle n;n.primary=false;f.owner->DidStartNavigation(&n);assert(f.ended==0);n.primary=true;f.owner->DidStartNavigation(&n);f.compositor.Deliver(0);assert(f.ended==1&&f.reason==Reason::kNavigationStarted);}
 {Fixture f;f.Start();f.Frame();Page page;f.owner->PrimaryPageWillBeDeactivated(page);f.compositor.Deliver(0);assert(f.reason==Reason::kPrimaryPageChanged&&f.ended==1);}
 {Fixture f;f.Start();f.Frame();Page page;f.owner->PrimaryPageChanged(page);assert(f.ended==1);}
 {Fixture f;f.Start();f.Frame();f.owner->OnVisibilityChanged(Visibility::VISIBLE);assert(f.ended==0);f.owner->OnVisibilityChanged(Visibility::HIDDEN);assert(f.ended==1&&f.reason==Reason::kHidden);}
 {Fixture f;f.Start();f.Frame();RenderFrameHost other;other.id.id++;f.owner->RenderFrameDeleted(&other);assert(f.ended==0);f.owner->RenderFrameDeleted(&f.wc.frame);assert(f.ended==1);}
 {Fixture f;f.Start();f.Frame();f.owner->PrimaryMainFrameRenderProcessGone(base::TERMINATION_STATUS_PROCESS_CRASHED);assert(f.ended==1);}
 {Fixture f;f.Start();f.Frame();f.owner->WebContentsDestroyed();f.compositor.Deliver(0);assert(f.ended==1&&f.reason==Reason::kDestroyed);}
 // Completion can delete its owner; no post-callback member access.
 {Fixture f;auto t=CaptureNativePageHandoffTarget(f.wc,1);f.owner=std::make_unique<Owner>(f.wc,*t,[&](){return f.scene;},[&](Reason, auto){f.ended++;f.owner.reset();});f.Frame();f.compositor.Deliver(0);assert(f.ended==1&&!f.owner);}
 // Provider can destroy this owner; its callback state remains locally retained.
 {Fixture f;auto t=CaptureNativePageHandoffTarget(f.wc,1);f.owner=std::make_unique<Owner>(f.wc,*t,[&](){f.owner.reset();return f.scene;},[&](Reason, auto){f.ended++;});f.Frame();assert(f.ended==0&&!f.owner&&f.compositor.callbacks.empty());}
 // Ordinary unique_ptr destruction does not notify a callback that resets it.
 {Fixture f;auto t=CaptureNativePageHandoffTarget(f.wc,1);int calls=0;
  {std::unique_ptr<Owner> slot;
   slot=std::make_unique<Owner>(f.wc,*t,[&](){return f.scene;},[&](Reason, auto){calls++;slot.reset();});}
  assert(calls==0);
 }
 // A provider may revoke the operation reentrantly; no frame request follows.
 {Fixture f;auto t=CaptureNativePageHandoffTarget(f.wc,1);f.owner=std::make_unique<Owner>(f.wc,*t,[&](){f.owner->Revoke(Reason::kCancelled);return f.scene;},[&](Reason, auto){f.ended++;});f.Frame();assert(f.ended==1&&f.compositor.callbacks.empty());}
}
'''
class ObservationOwner(unittest.TestCase):
 def _compile_run(self, code=None, success=True, sanitize=False, main=MAIN):
  stub=snapshot.STUB.replace('gfx::Size viewport_size_in_pixels;};','gfx::Size viewport_size_in_pixels;'+METADATA_FIELDS+'};')
  stub=stub.replace('struct NavigationController {NavigationEntryImpl entry;','struct NavigationController {bool pending=false;auto* GetPendingEntry(){return pending?&entry:nullptr;}NavigationEntryImpl entry;')
  with tempfile.TemporaryDirectory() as directory:
   out=pathlib.Path(directory);(out/'stub.h').write_text(stub+EXTRA)
   texts=[CC.read_text(),HH.read_text(),snapshot.CC.read_text(),snapshot.HH.read_text()]
   includes=set(re.findall(r'#include "([^"]+)"','\n'.join(texts)))
   actual={str(path.relative_to(BASE)):path.read_text() for path in (HH,snapshot.HH)}
   for name in includes:
    dest=out/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(actual.get(name,'#include "stub.h"\n'))
   (out/'main.cc').write_text(main)
   source=CC
   if code is not None:
    source=out/'owner.cc';source.write_text(code)
   flags=['-fsanitize=address,undefined','-fno-omit-frame-pointer'] if sanitize else []
   result=subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror',*flags,'-include',str(out/'stub.h'),'-I',str(out),str(source),str(snapshot.CC),str(out/'main.cc'),'-o',str(out/'test')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   # This executor is traced; LSan cannot inspect threads under ptrace. ASan/UBSan remain enabled.
   env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0')
   executed=subprocess.run([str(out/'test')],capture_output=True,text=True,env=env)
   if success:self.assertEqual(executed.returncode,0,executed.stderr)
   else:self.assertNotEqual(executed.returncode,0)
   return executed
 def test_exact_pinned_signature_declarations(self):
  fixture=ROOT/'experiments/single-handoff/fixtures/presentation-metadata-signature.json.gz'
  evidence=json.loads(gzip.decompress(fixture.read_bytes()))
  self.assertEqual(evidence['pin'],'d331de35ca8ab1358c7a17e4bd41627d55eaef51')
  for item in evidence['files'].values():self.assertEqual(hashlib.sha256(item['source'].encode()).hexdigest(),item['sha256'])
  header=evidence['files']['cc/trees/render_frame_metadata.h']['source']
  source=evidence['files']['cc/trees/render_frame_metadata.cc']['source']
  body=source.split('bool BrowserControlsMetadata::operator==(',1)[1].split('bool BrowserControlsMetadata::RequiresNewLocalSurfaceId',1)[0]
  self.assertNotIn('has_offset_tag',body)
  signature=CC.read_text().split('bool SameObservation(',1)[1].split('}  // namespace',1)[0]
  for field in re.findall(r'\b(?:x|xc)\.([a-z_]+)',signature):self.assertRegex(header,r'\b'+field+r'\b')
 def test_actual_source_with_api_doubles(self):
  self._compile_run()
 def test_stale_frame_regression_rejects_missing_revocation(self):
  mutated=CC.read_text().replace('  weak_factory_.InvalidateWeakPtrs();','')
  self.assertNotEqual(mutated,CC.read_text());self._compile_run(mutated,False)
 def test_missing_offset_authority_is_rejected(self):
  mutated=CC.read_text().replace('      xc.has_offset_tag == yc.has_offset_tag &&\n','')
  self.assertNotEqual(mutated,CC.read_text());self._compile_run(mutated,False)
 def test_whole_metadata_quiet_page_requirement_is_rejected(self):
  code=CC.read_text();a=code.index('  // Inspect independently');b=code.index('\n}',a)
  mutated=code[:a]+'  return a.embedded_surface == b.embedded_surface && a.activated_metadata == b.activated_metadata;'+code[b:]
  self._compile_run(mutated,False)
 def test_actual_source_under_memory_sanitizers(self):
  self._compile_run(sanitize=True)


 def test_destructor_regression_rejects_external_notification(self):
  source=CC.read_text();start=source.index('NativePageHandoffObservationOwner::~NativePageHandoffObservationOwner() {')
  end=source.index('\n}',start)+2
  mutated=source[:start]+"NativePageHandoffObservationOwner::~NativePageHandoffObservationOwner() {\n  Complete(EndReason::kDestroyed);\n}"+source[end:]
  reproducer=MAIN[:MAIN.index('int main(){')]+r"""
int main(){Fixture f;auto t=CaptureNativePageHandoffTarget(f.wc,1);int calls=0;
 {std::unique_ptr<Owner> slot;
  slot=std::make_unique<Owner>(f.wc,*t,[&](){return f.scene;},[&](Reason, auto){calls++;slot.reset();});}
 assert(calls==0);
}
"""
  result=self._compile_run(mutated,False,sanitize=True,main=reproducer)
  self.assertIn('AddressSanitizer',result.stderr)
  self.assertTrue('heap-use-after-free' in result.stderr or 'double-free' in result.stderr,result.stderr)
