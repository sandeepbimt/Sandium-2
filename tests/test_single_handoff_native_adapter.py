"""Compile actual dormant adapter methods with explicit lifecycle/JNI doubles."""
import pathlib,importlib.util,gzip,json,hashlib,subprocess,tempfile,unittest,os
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('adapter',ROOT/'experiments/single-handoff/native_adapter.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
STUB=r'''
#include <cassert>
#include <cstdint>
#include <memory>
#include <optional>
#include <functional>
#include <utility>
#include <vector>
using JNIEnv=int;using jobject=void*;
template<class T>using scoped_refptr=std::shared_ptr<T>;
#define FROM_HERE 0
namespace base {
template<class T>struct WeakState{T* ptr;};
template<class T>class WeakPtr {std::weak_ptr<WeakState<T>> p;public:WeakPtr()=default;explicit WeakPtr(std::shared_ptr<WeakState<T>> v):p(v){}T* get()const{auto s=p.lock();return s?s->ptr:nullptr;}operator bool()const{return get()!=nullptr;}T* operator->()const{return get();}void reset(){p.reset();}};
template<class T>class WeakPtrFactory {T* ptr;std::shared_ptr<WeakState<T>> s;public:explicit WeakPtrFactory(T* x):ptr(x),s(std::make_shared<WeakState<T>>(WeakState<T>{x})){}~WeakPtrFactory(){s->ptr=nullptr;}WeakPtr<T> GetWeakPtr(){return WeakPtr<T>(s);}void InvalidateWeakPtrs(){s->ptr=nullptr;s=std::make_shared<WeakState<T>>(WeakState<T>{ptr});}};
template<class C,class R,class... A,class... B>auto BindOnce(R(C::*fn)(A...),WeakPtr<C> weak,B... bound){return [=](auto&&... rest){if(weak)(weak.get()->*fn)(bound...,std::forward<decltype(rest)>(rest)...);};}
template<class F,class...B>auto BindRepeating(F f,B...b){return [=](){return f(b...);};}
struct SingleThreadTaskRunner {static inline std::vector<std::function<void()>> tasks;static auto* GetCurrentDefault(){static SingleThreadTaskRunner r;return &r;}template<class F>void PostTask(int,F f){tasks.emplace_back(f);}static void Drain(){auto q=std::move(tasks);tasks.clear();for(auto& f:q)f();}};
namespace android {template<class T>struct JavaRef{T value{};JavaRef()=default;JavaRef(T v):value(v){}bool is_null()const{return !value;}};inline JNIEnv* AttachCurrentThread(){return nullptr;}}
}
namespace cc::slim {struct Layer {Layer* up=nullptr;Layer* parent(){return up;}};}
namespace content {struct BrowserThread {enum ID{UI};static inline bool ui=true;static bool CurrentlyOn(ID){return ui;}};struct NativePageHandoffTarget{};struct NativePageHandoffSurfaceObservation{};class Compositor{};struct Controller {bool pending=false;void* GetPendingEntry(){return pending?this:nullptr;}};struct WebContents {bool eligible=true;Controller controller;base::WeakPtrFactory<WebContents> weak{this};static auto* FromJavaWebContents(const base::android::JavaRef<jobject>& x){return static_cast<WebContents*>(x.value);}auto& GetController(){return controller;}auto GetWeakPtr(){return weak.GetWeakPtr();}};inline std::optional<NativePageHandoffTarget> CaptureNativePageHandoffTarget(WebContents& c,int64_t){return c.eligible?std::optional<NativePageHandoffTarget>(NativePageHandoffTarget{}):std::nullopt;}
struct NativePageHandoffObservationOwner {enum class EndReason{kPresentationObserved,kCancelled,kFrameSinkLost,kTargetChanged,kSceneChanged,kHidden,kSecurityDestination};using SceneProvider=std::function<scoped_refptr<cc::slim::Layer>()>;using Completion=std::function<void(EndReason,std::optional<NativePageHandoffSurfaceObservation>)>;SceneProvider scene;Completion completion;NativePageHandoffObservationOwner(WebContents&,NativePageHandoffTarget,SceneProvider s,Completion c):scene(std::move(s)),completion(std::move(c)){}void Revoke(EndReason r){auto c=std::move(completion);if(c)c(r,std::nullopt);}void Present(){auto c=std::move(completion);if(c)c(EndReason::kPresentationObserved,NativePageHandoffSurfaceObservation{});}};
}
namespace android {using base::android::JavaRef;struct SceneLayer {scoped_refptr<cc::slim::Layer> value=std::make_shared<cc::slim::Layer>();static auto* FromJavaObject(JNIEnv*,const JavaRef<jobject>& o){return static_cast<SceneLayer*>(o.value);}auto layer(){return value;}};class CompositorView;
static SceneLayer* java_scene=nullptr;static std::function<void()> scene_hook;static std::function<void(int64_t,bool)> completion_hook;static int calls=0;static bool last_presented=false;
static JavaRef<jobject> Java_CompositorView_getSandiumNativeHandoffScene(JNIEnv*,const JavaRef<jobject>&,int64_t){auto hook=scene_hook;if(hook)hook();return JavaRef<jobject>(java_scene);}
static void Java_CompositorView_onSandiumNativeHandoffComplete(JNIEnv*,const JavaRef<jobject>&,int64_t token,bool presented){calls++;last_presented=presented;auto hook=completion_hook;if(hook)hook(token,presented);}
class CompositorView {public:
'''
TAIL=r'''
JavaRef<jobject> obj_;std::unique_ptr<content::Compositor> compositor_=std::make_unique<content::Compositor>();scoped_refptr<cc::slim::Layer> root_layer_=std::make_shared<cc::slim::Layer>();bool overlay_video_mode_=false,overlay_immersive_ar_mode_=false,overlay_xr_full_screen_mode_=false;
CompositorView(){sandium_surface_ready_=true;}
~CompositorView(){sandium_handoff_weak_factory_.InvalidateWeakPtrs();sandium_handoff_token_=0;sandium_handoff_contents_.reset();sandium_handoff_owner_.reset();sandium_selected_scene_.reset();}
};
'''
MAIN=r'''
}
int main(){using namespace android;content::WebContents wc;JavaRef<jobject> jw(&wc);auto* v=new CompositorView;SceneLayer scene;scene.value->up=v->root_layer_.get();v->sandium_selected_scene_=scene.value;java_scene=&scene;
content::BrowserThread::ui=false;assert(!v->BeginSandiumNativeHandoff(nullptr,1,jw));content::BrowserThread::ui=true;
assert(!v->BeginSandiumNativeHandoff(nullptr,0,jw));wc.eligible=false;assert(!v->BeginSandiumNativeHandoff(nullptr,1,jw));wc.eligible=true;assert(!v->BeginSandiumNativeHandoff(nullptr,1,jw));assert(calls==0);assert(v->BeginSandiumNativeHandoff(nullptr,2,jw));assert(!v->BeginSandiumNativeHandoff(nullptr,3,jw));assert(calls==0);assert(v->GetSandiumNativeHandoffScene(2)==scene.value);
v->CancelSandiumNativeHandoff(nullptr,99);assert(v->sandium_handoff_token_==2);v->CancelSandiumNativeHandoff(nullptr,2);assert(!v->sandium_handoff_owner_&&v->sandium_handoff_token_==0&&calls==0);assert(v->BeginSandiumNativeHandoff(nullptr,4,jw));base::SingleThreadTaskRunner::Drain();assert(calls==1&&!last_presented&&v->sandium_handoff_token_==4);
// Actual selected native layer must still be current and directly under root.
SceneLayer replacement;java_scene=&replacement;assert(!v->GetSandiumNativeHandoffScene(4));java_scene=nullptr;assert(!v->GetSandiumNativeHandoffScene(4));java_scene=&scene;scene.value->up=nullptr;assert(!v->GetSandiumNativeHandoffScene(4));scene.value->up=v->root_layer_.get();
// Query reentry cancels owner: no stale scene escapes.
scene_hook=[&](){v->CancelSandiumNativeHandoff(nullptr,4);};assert(!v->GetSandiumNativeHandoffScene(4));scene_hook={};base::SingleThreadTaskRunner::Drain();assert(calls==2);
// Completion clears state before external code, allowing a new begin safely.
assert(v->BeginSandiumNativeHandoff(nullptr,5,jw));completion_hook=[&](int64_t token,bool presented){assert(token==5&&presented);assert(!v->sandium_handoff_owner_&&!v->sandium_handoff_token_);assert(v->BeginSandiumNativeHandoff(nullptr,6,jw));};v->sandium_handoff_owner_->Present();completion_hook={};assert(calls==3&&v->sandium_handoff_token_==6);
// Normal completion may destroy adapter; no access follows external callback.
completion_hook=[&](int64_t,bool){delete v;v=nullptr;};v->sandium_handoff_owner_->Present();completion_hook={};assert(v==nullptr&&calls==4);
// Queued revoke notification is inert after native destruction (Java teardown owns lease).
v=new CompositorView;assert(v->BeginSandiumNativeHandoff(nullptr,1,jw));v->CancelSandiumNativeHandoff(nullptr,1);delete v;v=nullptr;base::SingleThreadTaskRunner::Drain();assert(calls==4);
// Java scene query may delete adapter; post-JNI WeakPtr prevents UAF.
v=new CompositorView;assert(v->BeginSandiumNativeHandoff(nullptr,1,jw));scene_hook=[&](){delete v;v=nullptr;};auto* querying=v;assert(!querying->GetSandiumNativeHandoffScene(1));scene_hook={};assert(v==nullptr);
// Rejected readiness/pending/overlay has no callback or ownership transfer.
v=new CompositorView;wc.controller.pending=true;assert(!v->BeginSandiumNativeHandoff(nullptr,1,jw));wc.controller.pending=false;v->sandium_draw_paused_=true;assert(!v->BeginSandiumNativeHandoff(nullptr,2,jw));v->sandium_draw_paused_=false;v->overlay_video_mode_=true;assert(!v->BeginSandiumNativeHandoff(nullptr,3,jw));delete v;assert(calls==4);
}
'''
class Adapter(unittest.TestCase):
 def fixtures(self):return json.loads(gzip.decompress((ROOT/'experiments/single-handoff/fixtures/native-handoff-adapter.json.gz').read_bytes()))['files']
 def test_full_exact_transform_and_replay(self):
  for path,item in self.fixtures().items():
   self.assertEqual(hashlib.sha256(item['source'].encode()).hexdigest(),item['sha256'])
   out=m.transform(path,item['source']);self.assertEqual(m.transform(path,out),out)
   required=m.PUBLIC if path==m.HEADER else m.METHODS
   with self.assertRaises(ValueError):m.transform(path,out.replace(required,required+'//drift',1).replace(m.MARKER,m.MARKER+'broken',1))
  with self.assertRaises(ValueError):m.transform(m.SOURCE,'unknown')
  wired=m.transform(m.SOURCE,self.fixtures()[m.SOURCE]['source'])
  with self.assertRaises(ValueError):m.transform(m.SOURCE,wired.replace('sandium_handoff_owner_->ObserveAtFinalization(*compositor_);','',1))
  with self.assertRaises(ValueError):m.transform(m.SOURCE,wired.replace('RevokeSandiumNativeHandoff(SandiumHandoffReason::kFrameSinkLost);','',1))
 def test_actual_methods_lifetimes_under_sanitizers(self):
  code=STUB+m.PUBLIC+m.PRIVATE+TAIL+m.METHODS+MAIN
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);(p/'main.cc').write_text(code)
   r=subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=address,undefined','-fno-omit-frame-pointer','-no-pie',str(p/'main.cc'),'-o',str(p/'run')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   r=subprocess.run([str(p/'run')],capture_output=True,text=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'});self.assertEqual(r.returncode,0,r.stderr)
 def test_candidate_java_native_layout_composition(self):
  here=ROOT/'experiments/single-handoff'
  modules={}
  for name in ('java_adapter','eligibility'):
   spec=importlib.util.spec_from_file_location(name,here/(name+'.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);modules[name]=module
  java=modules['java_adapter'];elig=modules['eligibility']
  original={p:item['source'] for p,item in self.fixtures().items()}
  j=json.loads(gzip.decompress((here/'fixtures/compositor-view-java.json.gz').read_bytes()))
  original[java.PATH]=j['text']
  for p,item in json.loads(gzip.decompress((here/'fixtures/static-layout-eligibility.json.gz').read_bytes()))['files'].items():original[p]=item['source']
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d)
   for p,text in original.items():dest=root/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
   plans=[elig.plan(root),java.plan(root),m.plan(root)]
   paths=[p for plan in plans for p in plan];self.assertEqual(len(paths),len(set(paths)))
   for plan in plans:
    for p,text in plan.items():p.write_text(text)
   for module in (elig,java,m):
    for p,text in module.plan(root).items():self.assertEqual(p.read_text(),text)
   jsource=(root/java.PATH).read_text();begin=jsource.index('    public void finalizeLayers(');end=jsource.index('    @Override',begin);body=jsource[begin:end]
   stages=['provider.getUpdatedActiveSceneLayer(', 'mSandiumFinalizedScene = sceneLayer;', 'CompositorViewJni.get().setSceneLayer(', 'CompositorViewJni.get().finalizeLayers(']
   positions=[body.index(x) for x in stages];self.assertEqual(positions,sorted(positions))
   source=(root/m.SOURCE).read_text();begin=source.index('void CompositorView::FinalizeLayers(');end=source.index('\n}',begin);body=source[begin:end]
   self.assertLess(body.index('OnFrameUpdatesFinished()'),body.index('ObserveAtFinalization('))
   self.assertIn('boolean beginSandiumNativeHandoff(',jsource);self.assertIn('bool CompositorView::BeginSandiumNativeHandoff(',source)
   self.assertIn('onSandiumNativeHandoffComplete(long token, boolean presented)',jsource)
   self.assertIn('Java_CompositorView_onSandiumNativeHandoffComplete(env, obj_, token, presented)',source)
 def test_boundaries_and_no_private_content_include(self):
  source=m.transform(m.SOURCE,self.fixtures()[m.SOURCE]['source'])
  header=m.transform(m.HEADER,self.fixtures()[m.HEADER]['source'])
  self.assertNotIn('#include "content/browser/',source+header)
  self.assertNotIn('native_adapter',(ROOT/'experiments/single-handoff/apply.py').read_text())
  for anchor in ('SurfaceCreated','SurfaceDestroyed','RecreateSurface','OnTabChanged'):
   start=source.index('void CompositorView::'+anchor+'(');self.assertIn('RevokeSandiumNativeHandoff',source[start:source.index('\n}',start)])
  self.assertIn('ObserveAtFinalization(*compositor_); // LAST',source)
  self.assertIn('SceneLayer::FromJavaObject(env, java_scene)',m.METHODS)
  self.assertNotIn('scene_layer_->',m.METHODS)
if __name__=='__main__':unittest.main()
