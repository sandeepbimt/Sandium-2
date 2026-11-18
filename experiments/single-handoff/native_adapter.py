"""Dormant CompositorView adapter. No installed planner/GN/JNI activation."""
from pathlib import Path
HEADER = "chrome/browser/android/compositor/compositor_view.h"
SOURCE = "chrome/browser/android/compositor/compositor_view.cc"
MARKER = "SANDIUM_NATIVE_HANDOFF_ADAPTER_V1"
PUBLIC = """  // SANDIUM_NATIVE_HANDOFF_ADAPTER_V1
  bool BeginSandiumNativeHandoff(JNIEnv* env, int64_t token,
      const base::android::JavaRef<jobject>& jweb_contents);
  void CancelSandiumNativeHandoff(JNIEnv* env, int64_t token);
"""
PRIVATE = """  using SandiumHandoffReason = content::NativePageHandoffObservationOwner::EndReason;
  scoped_refptr<cc::slim::Layer> GetSandiumNativeHandoffScene(int64_t token);
  void CompleteSandiumNativeHandoff(int64_t token, SandiumHandoffReason reason,
      std::optional<content::NativePageHandoffSurfaceObservation> observation);
  void RevokeSandiumNativeHandoff(SandiumHandoffReason reason);
  void NotifySandiumNativeHandoff(int64_t token, bool presented);
  int64_t sandium_handoff_token_ = 0;
  int64_t sandium_last_handoff_token_ = 0;
  bool sandium_surface_ready_ = false;
  bool sandium_draw_paused_ = false;
  base::WeakPtr<content::WebContents> sandium_handoff_contents_;
  scoped_refptr<cc::slim::Layer> sandium_selected_scene_;
  std::unique_ptr<content::NativePageHandoffObservationOwner> sandium_handoff_owner_;
  // Last: weak callbacks become inert before other members are destroyed.
  base::WeakPtrFactory<CompositorView> sandium_handoff_weak_factory_{this};
"""
METHODS = r"""
// SANDIUM_NATIVE_HANDOFF_ADAPTER_V1
bool CompositorView::BeginSandiumNativeHandoff(JNIEnv* env, int64_t token,
    const base::android::JavaRef<jobject>& jweb_contents) {
  if (!content::BrowserThread::CurrentlyOn(content::BrowserThread::UI)) return false;
  if (token <= 0 || token <= sandium_last_handoff_token_) return false;
  sandium_last_handoff_token_ = token;
  // Begin never invokes Java or completion. False transfers no lease ownership.
  if (sandium_handoff_token_ || !compositor_ || !sandium_surface_ready_ ||
      sandium_draw_paused_ || overlay_video_mode_ || overlay_immersive_ar_mode_ ||
      overlay_xr_full_screen_mode_) return false;
  auto* contents = content::WebContents::FromJavaWebContents(jweb_contents);
  if (!contents || contents->GetController().GetPendingEntry()) return false;
  auto target = content::CaptureNativePageHandoffTarget(*contents, token);
  if (!target) return false;
  sandium_handoff_token_ = token;
  sandium_handoff_contents_ = contents->GetWeakPtr();
  sandium_handoff_owner_ = std::make_unique<content::NativePageHandoffObservationOwner>(
      *contents, *target,
      base::BindRepeating(
          [](base::WeakPtr<CompositorView> view, int64_t expected)
              -> scoped_refptr<cc::slim::Layer> {
            return view ? view->GetSandiumNativeHandoffScene(expected) : nullptr;
          }, sandium_handoff_weak_factory_.GetWeakPtr(), token),
      base::BindOnce(&CompositorView::CompleteSandiumNativeHandoff,
          sandium_handoff_weak_factory_.GetWeakPtr(), token));
  return true;
}
void CompositorView::CancelSandiumNativeHandoff(JNIEnv* env, int64_t token) {
  if (!content::BrowserThread::CurrentlyOn(content::BrowserThread::UI)) return;
  if (token != sandium_handoff_token_ || !token) return;
  RevokeSandiumNativeHandoff(SandiumHandoffReason::kCancelled);
}
scoped_refptr<cc::slim::Layer> CompositorView::GetSandiumNativeHandoffScene(int64_t token) {
  if (token != sandium_handoff_token_ || !token || !sandium_handoff_contents_ ||
      !sandium_surface_ready_ || sandium_draw_paused_ || overlay_video_mode_ ||
      overlay_immersive_ar_mode_ || overlay_xr_full_screen_mode_) return nullptr;
  auto weak = sandium_handoff_weak_factory_.GetWeakPtr();
  JNIEnv* env = base::android::AttachCurrentThread();
  // This Java query may reenter cancellation/destruction. Do not use this after it.
  auto java_scene = Java_CompositorView_getSandiumNativeHandoffScene(env, obj_, token);
  if (!weak || weak->sandium_handoff_token_ != token) return nullptr;
  // Resolve native liveness afresh. A destroyed SceneLayer's Java native pointer
  // is zero even if its refcounted layer remains attached beneath root_layer_.
  auto* scene = SceneLayer::FromJavaObject(env, java_scene);
  if (!scene) return nullptr;
  auto layer = scene->layer();
  if (!layer || layer != weak->sandium_selected_scene_ ||
      layer->parent() != weak->root_layer_.get()) return nullptr;
  return layer;
}
void CompositorView::CompleteSandiumNativeHandoff(int64_t token,
    SandiumHandoffReason reason,
    std::optional<content::NativePageHandoffSurfaceObservation> observation) {
  if (!token || token != sandium_handoff_token_) return;
  const bool presented = reason == SandiumHandoffReason::kPresentationObserved &&
      observation.has_value();
  sandium_handoff_token_ = 0;
  sandium_handoff_contents_.reset();
  auto retired = std::move(sandium_handoff_owner_);
  retired.reset(); // Owner completion permits deletion and performs no further member access.
  NotifySandiumNativeHandoff(token, presented); // LAST: Java may destroy this object.
}
void CompositorView::NotifySandiumNativeHandoff(int64_t token, bool presented) {
  JNIEnv* env = base::android::AttachCurrentThread();
  Java_CompositorView_onSandiumNativeHandoffComplete(env, obj_, token, presented);
  // No member access after external code.
}
void CompositorView::RevokeSandiumNativeHandoff(SandiumHandoffReason reason) {
  if (!sandium_handoff_token_) return;
  const int64_t token = sandium_handoff_token_;
  sandium_handoff_token_ = 0;
  sandium_handoff_contents_.reset();
  auto retired = std::move(sandium_handoff_owner_);
  if (retired) retired->Revoke(reason); // Old callback sees cleared token; no JNI.
  retired.reset();
  // Mutation callers continue native work after this returns. Never synchronously
  // call Java here: Java could delete this before that caller finishes its work.
  base::SingleThreadTaskRunner::GetCurrentDefault()->PostTask(FROM_HERE,
      base::BindOnce(&CompositorView::NotifySandiumNativeHandoff,
          sandium_handoff_weak_factory_.GetWeakPtr(), token, false));
}
"""
def once(s, old, new):
    if s.count(old) != 1: raise ValueError("Native adapter anchor drift: " + old[:100])
    return s.replace(old,new,1)
def transform(path,s):
    if path not in (HEADER,SOURCE): raise ValueError("Unknown adapter source")
    if MARKER in s:
        required=PUBLIC if path==HEADER else METHODS
        if s.count(MARKER)!=1 or required not in s: raise ValueError("Partial native adapter")
        if path == HEADER:
            if PRIVATE not in s or '#include "content/public/browser/android/native_page_handoff_observation_owner.h"' not in s:
                raise ValueError("Partial native adapter declarations")
        else:
            for reason, count in (("kFrameSinkLost", 5), ("kTargetChanged", 4),
                                  ("kSceneChanged", 1), ("kHidden", 1),
                                  ("kSecurityDestination", 3)):
                if s.count("RevokeSandiumNativeHandoff(SandiumHandoffReason::" + reason + ");") != count:
                    raise ValueError("Partial native adapter boundary: " + reason)
            for token in ('sandium_handoff_owner_->ObserveAtFinalization(*compositor_); // LAST: may complete/reenter.',
                          'sandium_selected_scene_ = std::move(selected);',
                          'sandium_surface_ready_ = true;',
                          'sandium_handoff_owner_.reset(); // Silent; Java holder teardown owns resource cleanup.',
                          '#include "content/public/browser/browser_thread.h"'):
                if s.count(token) != 1: raise ValueError("Partial native adapter wiring: " + token)
        return s
    if path==HEADER:
        s=once(s,'#include <jni.h>','#include <jni.h>\n#include <cstdint>\n#include <memory>\n#include <optional>\n#include "content/public/browser/android/native_page_handoff_observation_owner.h"')
        s=once(s,'  void FinalizeLayers(JNIEnv* env);',PUBLIC+'  void FinalizeLayers(JNIEnv* env);')
        s=once(s,'  bool overlay_xr_full_screen_mode_;','  bool overlay_xr_full_screen_mode_;\n'+PRIVATE)
        return s
    s=once(s,'#include "base/functional/bind.h"','#include "base/functional/bind.h"\n#include "base/location.h"\n#include "base/task/single_thread_task_runner.h"\n#include "content/public/browser/navigation_controller.h"\n#include "content/public/browser/browser_thread.h"')
    s=once(s,'CompositorView::~CompositorView() {','CompositorView::~CompositorView() {\n  sandium_handoff_weak_factory_.InvalidateWeakPtrs();\n  sandium_handoff_token_ = 0;\n  sandium_handoff_contents_.reset();\n  sandium_handoff_owner_.reset(); // Silent; Java holder teardown owns resource cleanup.\n  sandium_selected_scene_.reset();')
    # Defer boundary notifications, leaving native mutation behavior unchanged.
    for anchor in ('void CompositorView::RecreateSurface() {','void CompositorView::SurfaceCreated(JNIEnv* env) {','void CompositorView::SurfaceDestroyed(JNIEnv* env) {'):
        s=once(s,anchor,anchor+'\n  sandium_surface_ready_ = false;\n  RevokeSandiumNativeHandoff(SandiumHandoffReason::kFrameSinkLost);')
    s=once(s,'  // Java View layout sometimes unexpectedly cause CompositorView to be sized so', '  RevokeSandiumNativeHandoff(SandiumHandoffReason::kFrameSinkLost);\n  sandium_surface_ready_ = false;\n  // Java View layout sometimes unexpectedly cause CompositorView to be sized so')
    s=once(s,'  return surface_handle;','  sandium_surface_ready_ = true;\n  return surface_handle;')
    for anchor in ('  gfx::Size size(width, height);','  web_contents->GetNativeView()->OnControlsResizeViewChanged(', '  gfx::Rect keyboard_rect(x, y, width, height);'):
        s=once(s,anchor,'  RevokeSandiumNativeHandoff(SandiumHandoffReason::kTargetChanged);\n'+anchor)
    for field in ('overlay_video_mode_','overlay_immersive_ar_mode_','overlay_xr_full_screen_mode_'):
        anchor='  '+field+' = enabled;'
        s=once(s,anchor,'  if ('+field+' != enabled)\n    RevokeSandiumNativeHandoff(SandiumHandoffReason::kSecurityDestination);\n'+anchor)
    anchor='  SceneLayer* scene_layer = SceneLayer::FromJavaObject(env, jscene_layer);'
    s=once(s,anchor,anchor+'\n  auto selected = scene_layer ? scene_layer->layer() : nullptr;\n  if (selected != sandium_selected_scene_)\n    RevokeSandiumNativeHandoff(SandiumHandoffReason::kSceneChanged);\n  sandium_selected_scene_ = std::move(selected);')
    s=once(s,'  compositor_->SetDrawPaused(paused);','  if (paused != sandium_draw_paused_)\n    RevokeSandiumNativeHandoff(SandiumHandoffReason::kHidden);\n  sandium_draw_paused_ = paused;\n  compositor_->SetDrawPaused(paused);')
    s=once(s,'  ui::WindowAndroid* wa =','  RevokeSandiumNativeHandoff(SandiumHandoffReason::kFrameSinkLost);\n  ui::WindowAndroid* wa =')
    s=once(s,'void CompositorView::OnTabChanged(JNIEnv* env) {','void CompositorView::OnTabChanged(JNIEnv* env) {\n  RevokeSandiumNativeHandoff(SandiumHandoffReason::kTargetChanged);')
    anchor='  TRACE_EVENT0("compositor", "CompositorView::FinalizeLayers");\n#endif\n}'
    s=once(s,anchor,'  TRACE_EVENT0("compositor", "CompositorView::FinalizeLayers");\n#endif\n  if (sandium_handoff_owner_ && compositor_)\n    sandium_handoff_owner_->ObserveAtFinalization(*compositor_); // LAST: may complete/reenter.\n}')
    return once(s,'}  // namespace android',METHODS+'\n}  // namespace android')
def plan(root):
    root=Path(root)
    return {root/p:transform(p,(root/p).read_text()) for p in (HEADER,SOURCE)}
