"""Compile the real dormant collector with explicit API doubles, not Android."""
import pathlib,re,subprocess,tempfile,unittest,json,gzip
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/'experiments/single-handoff/components'
CC=BASE/'content/browser/android/native_page_handoff_snapshot.cc'
HH=BASE/'content/public/browser/android/native_page_handoff_snapshot.h'
STUB=r"""
#pragma once
#include <optional>
#include <vector>
#include <cstdint>
#define CONTENT_EXPORT
namespace gfx {struct Size {int w=10,h=20;bool IsEmpty()const{return w<=0||h<=0;}bool operator==(const Size&)const=default;};}
namespace viz {struct FrameSinkId {int id=1;bool is_valid()const{return id>0;}bool operator==(const FrameSinkId&)const=default;};struct LocalSurfaceId {int id=2;bool is_valid()const{return id>0;}bool operator==(const LocalSurfaceId&)const=default;};struct SurfaceId {FrameSinkId f;LocalSurfaceId l;SurfaceId(FrameSinkId a={},LocalSurfaceId b={}):f(a),l(b){}bool operator==(const SurfaceId&)const=default;};}
namespace blink {struct DocumentToken {int id=3;bool operator==(const DocumentToken&)const=default;};}
namespace cc {struct RenderFrameMetadata {std::optional<viz::LocalSurfaceId> local_surface_id=viz::LocalSurfaceId{};int64_t primary_main_frame_item_sequence_number=4;gfx::Size viewport_size_in_pixels;};namespace slim {struct Layer {bool hidden=false;float alpha=1;bool draw=true;gfx::Size size;std::vector<Layer*> kids;bool hide_layer_and_subtree()const{return hidden;}float opacity()const{return alpha;}bool draws_content()const{return draw;}const auto& children()const{return kids;}const gfx::Size& bounds()const{return size;}};struct SurfaceLayer:Layer {viz::SurfaceId id;const auto& surface_id()const{return id;}};}}
namespace content {
struct GlobalRenderFrameHostId {int id=7;bool operator==(const GlobalRenderFrameHostId&)const=default;};
enum class Visibility {VISIBLE,HIDDEN};
struct BrowserThread {enum ID {UI};static inline bool on_ui=true;static bool CurrentlyOn(ID){return on_ui;}};
struct RenderFrameMetadataProvider {cc::RenderFrameMetadata metadata;const auto& LastRenderFrameMetadata(){return metadata;}};
struct RenderWidgetHostViewAndroid {cc::slim::SurfaceLayer layer;bool showing=true;viz::FrameSinkId sink;gfx::Size viewport;static auto* FromRenderWidgetHostView(RenderWidgetHostViewAndroid* x){return x;}bool IsShowing(){return showing;}const auto& GetFrameSinkId(){return sink;}const auto* GetSurfaceLayer(){return &layer;}gfx::Size GetCompositorViewportPixelSize(){return viewport;}};
struct RenderWidgetHostImpl {RenderWidgetHostViewAndroid view;RenderFrameMetadataProvider provider;int route=8;auto* GetView(){return &view;}int GetRoutingID(){return route;}auto* render_frame_metadata_provider(){return &provider;}};
struct URL {bool http=true;bool SchemeIsHTTPOrHTTPS(){return http;}};
struct FrameTreeNode {};
struct RenderFrameHostImpl {bool active=true,live=true,error=false;URL url;GlobalRenderFrameHostId id;blink::DocumentToken doc;RenderWidgetHostImpl widget;FrameTreeNode node;bool IsActive(){return active;}bool IsRenderFrameLive(){return live;}bool IsErrorDocument(){return error;}URL& GetLastCommittedURL(){return url;}auto* GetRenderWidgetHost(){return &widget;}auto* frame_tree_node(){return &node;}auto GetGlobalId(){return id;}const auto& GetDocumentToken(){return doc;}};
struct FrameNavigationEntry {int64_t item=4;int64_t item_sequence_number(){return item;}};
struct NavigationEntryImpl {FrameNavigationEntry frame;bool present=true;auto* GetFrameEntry(FrameTreeNode*){return present?&frame:nullptr;}};
struct NavigationController {NavigationEntryImpl entry;bool present=true;auto* GetLastCommittedEntry(){return present?&entry:nullptr;}};
struct WebContents {bool crashed=false;Visibility visibility=Visibility::VISIBLE;RenderFrameHostImpl frame;NavigationController controller;bool IsCrashed(){return crashed;}Visibility GetVisibility(){return visibility;}auto* GetPrimaryMainFrame(){return &frame;}auto& GetController(){return controller;}};
}
"""
MAIN=r"""
#include <cassert>
#include "content/public/browser/android/native_page_handoff_snapshot.h"
using namespace content;
int main(){WebContents wc;auto& view=wc.frame.widget.view;auto& meta=wc.frame.widget.provider.metadata;cc::slim::Layer root;root.kids={&view.layer};auto target=CaptureNativePageHandoffTarget(wc,1);assert(target);auto ok=[&](){return InspectNativePageHandoffSurface(wc,*target,1,root).has_value();};assert(ok());
assert(!CaptureNativePageHandoffTarget(wc,0));BrowserThread::on_ui=false;assert(!ok());BrowserThread::on_ui=true;
wc.frame.doc.id++;assert(!ok());wc.frame.doc.id--;wc.frame.id.id++;assert(!ok());wc.frame.id.id--;wc.frame.widget.route++;assert(!ok());wc.frame.widget.route--;assert(!InspectNativePageHandoffSurface(wc,*target,2,root));
wc.frame.error=true;assert(!ok());wc.frame.error=false;wc.frame.url.http=false;assert(!ok());wc.frame.url.http=true;wc.frame.active=false;assert(!ok());wc.frame.active=true;wc.frame.live=false;assert(!ok());wc.frame.live=true;wc.crashed=true;assert(!ok());wc.crashed=false;wc.visibility=Visibility::HIDDEN;assert(!ok());wc.visibility=Visibility::VISIBLE;
wc.controller.entry.frame.item=-1;assert(!CaptureNativePageHandoffTarget(wc,1));wc.controller.entry.frame.item=4;wc.controller.present=false;assert(!ok());wc.controller.present=true;
meta.primary_main_frame_item_sequence_number++;assert(!ok());meta.primary_main_frame_item_sequence_number--;meta.local_surface_id.reset();assert(!ok());meta.local_surface_id=viz::LocalSurfaceId{};
view.layer.id.l.id++;assert(!ok());view.layer.id.l.id--;view.layer.size.h++;assert(!ok());view.layer.size.h--;view.viewport.h++;assert(!ok());view.viewport.h--;meta.viewport_size_in_pixels.h=0;assert(!ok());meta.viewport_size_in_pixels.h=20;
view.sink.id++;assert(!ok());view.sink.id--;view.showing=false;assert(!ok());view.showing=true;wc.controller.entry.present=false;assert(!ok());wc.controller.entry.present=true;
cc::slim::Layer intermediate;intermediate.kids={&view.layer};root.kids={&intermediate};intermediate.hidden=true;assert(!ok());intermediate.hidden=false;assert(ok());root.kids={&view.layer};
root.hidden=true;assert(!ok());root.hidden=false;root.alpha=.5;assert(!ok());root.alpha=1;root.kids.clear();assert(!ok());root.kids={&view.layer};view.layer.draw=false;assert(!ok());view.layer.draw=true;assert(ok());
// Same-document history change rejects earlier target even with identical doc token.
wc.controller.entry.frame.item=5;meta.primary_main_frame_item_sequence_number=5;assert(!ok());
}
"""
class Snapshot(unittest.TestCase):
 def test_actual_source_with_explicit_api_doubles(self):
  with tempfile.TemporaryDirectory() as d:
   out=pathlib.Path(d);(out/'stub.h').write_text(STUB)
   includes=set(re.findall(r'#include "([^"]+)"',CC.read_text()+HH.read_text()))
   for name in includes:
    dest=out/name;dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(HH.read_text() if name.endswith('native_page_handoff_snapshot.h') else '#include "stub.h"\n')
   (out/'main.cc').write_text(MAIN)
   r=subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-include',str(out/'stub.h'),'-I',d,str(CC),str(out/'main.cc'),'-o',str(out/'test')],capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr)
   subprocess.run([str(out/'test')],check=True)
 def test_dormant_and_value_only_boundary(self):
  self.assertNotIn('native_page_handoff_snapshot', (ROOT/'experiments/single-handoff/apply.py').read_text())
  self.assertNotIn('content/browser/',HH.read_text())
  self.assertNotIn('SurfaceLayer*',HH.read_text())
  self.assertNotIn('RequestSuccessfulPresentation',CC.read_text())
 def test_pinned_api_evidence(self):
  evidence=json.loads(gzip.decompress((ROOT/'experiments/single-handoff/fixtures/native-handoff-api.json.gz').read_bytes()))
  self.assertEqual(evidence['pin'],'d331de35ca8ab1358c7a17e4bd41627d55eaef51')
  for item in evidence['files']:
   self.assertEqual(len(item['sha256']),64)
   self.assertTrue(item['excerpts'])
if __name__=='__main__':unittest.main()
