"""Held numeric transition producers. Requires reviewed ContentBrowserClient bridge.
No CLI writer, no product activation, no changes to animation decisions.
"""
from pathlib import Path
BLUR='content/browser/navigation_transitions/blur_transition_animation_manager.cc'
BACK='content/browser/navigation_transitions/back_forward_transition_animator.cc'
CHANGES=[]
def add(path,old,new):CHANGES.append((path,old,new))
def values(expressions):return ', '.join('static_cast<double>('+x+')' for x in expressions)
def emit(wc,event,nav,fields,indent='  ',time='base::TimeTicks::Now()'):
 return '\n'+indent+'''{ // SANDIUM_TRANSITION_RING_V1: UI/private/recording gate before payload work.
'''+indent+'  auto* sandium_wc = '+wc+';\n'+indent+'''  auto* sandium_client = GetContentClient()->browser();
'''+indent+'''  if (sandium_client->IsSandiumNavigationDiagnosticsEnabled(sandium_wc)) {
'''+indent+f'''    sandium_client->RecordSandiumNavigationDiagnostic(sandium_wc, {event},
'''+indent+'        '+nav+', '+time+'.since_origin().InMicroseconds(),\n'+indent+'        std::vector<double>{'+values(fields)+'});\n'+indent+'  }\n'+indent+'}\n'
def blur(stage,detail='-1',nav='navigation_id_'):
 return emit('web_contents()',21,nav,[str(stage),'static_cast<int>(animation_state_)',detail,'blur_layer_ != nullptr','fallback_color_layer_ != nullptr','blur_layer_ ? blur_layer_->bounds().width() : 0','blur_layer_ ? blur_layer_->bounds().height() : 0','GetWebContentsViewAndroidDelegate() ? GetWebContentsViewAndroidDelegate()->GetTopControlsHeight() : 0'])
WC='animation_manager_->web_contents_view_android()->web_contents()'
NAV='tracked_request_ ? tracked_request_->navigation_id : 0'
def back(stage,detail='-1',time='base::TimeTicks::Now()'):
 return emit(WC,22,NAV,[str(stage),'static_cast<int>(state_)','static_cast<int>(navigation_state_)',detail,'fallback_ux_.has_value()','is_copied_from_embedder_','screenshot_layer_ ? screenshot_layer_->bounds().width() : 0','screenshot_layer_ ? screenshot_layer_->bounds().height() : 0'],time=time)
def layer(wc,nav,expr,stage,top,view,kind):
 # Local layer positions, NEVER claim absolute/window coordinates. The native
 # transform identity flag identifies rows needing deeper matrix instrumentation.
 return '\n  { // SANDIUM_TRANSITION_RING_V1: bounded local ancestry, no string matrices.\n    auto* sandium_wc = '+wc+''';
    auto* sandium_client = GetContentClient()->browser();
    if (sandium_client->IsSandiumNavigationDiagnosticsEnabled(sandium_wc)) {
      cc::slim::Layer* sandium_layer = '''+expr+''';
      for (int depth = 0; sandium_layer && depth < 16; ++depth) {
        sandium_client->RecordSandiumNavigationDiagnostic(sandium_wc, 23,
            '''+nav+''', base::TimeTicks::Now().since_origin().InMicroseconds(),
            std::vector<double>{'''+values([str(stage),'depth','sandium_layer->position().x()','sandium_layer->position().y()','sandium_layer->bounds().width()','sandium_layer->bounds().height()','sandium_layer->transform().IsIdentity()','sandium_layer->opacity()','sandium_layer->parent() != nullptr',top,view+'->GetPhysicalBackingSize().width()',view+'->GetPhysicalBackingSize().height()',view+'->GetDipScale()',str(kind),'depth == 15 && sandium_layer->parent() != nullptr','0'])+'''});
        sandium_layer = sandium_layer->parent();
      }
    }
  }
'''
for path in (BLUR,BACK):
 anchor='#include "base/metrics/histogram_functions.h"'
 add(path,anchor,anchor+'\n#include <vector>'+('\n#include "base/time/time.h"' if path==BLUR else ''))
# Blur product already includes both client headers for destination dark policy.
anchor='#include "content/public/browser/content_browser_client.h"'
add(BACK,anchor,anchor+'\n#include "content/public/common/content_client.h"')
# Native/product-composed ordinary blur anchors.
anchor='''  // If there's an existing animation from a previous navigation, stop it'''
add(BLUR,anchor,blur(0,'(navigation_handle->IsSameDocument() ? 1 : 0) | (navigation_handle->IsServedFromBackForwardCache() ? 2 : 0) | (navigation_handle->GetReloadType() != ReloadType::NONE ? 4 : 0)','navigation_handle->GetNavigationId()')+'\n'+anchor)
anchor='''  TRACE_EVENT("navigation", "SandiumOrdinaryBlurSource",
              "native_pixels", native_pixels, "outgoing_web", outgoing_web);'''
add(BLUR,anchor,anchor+blur(1,'(native_pixels ? 1 : 0) | (outgoing_web ? 2 : 0) | (surface_id.is_valid() ? 4 : 0)','navigation_handle->GetNavigationId()'))
anchor='  animation_state_ = state;'
add(BLUR,anchor,anchor+blur(2))
anchor='''void BlurTransitionAnimationManager::RecordExitReason(
    TransitionExitReason exit_reason) {'''
add(BLUR,anchor,anchor+blur(3,'static_cast<int>(exit_reason)'))
anchor='void BlurTransitionAnimationManager::OnBlurHoldTimerExpired() {'
add(BLUR,anchor,anchor+blur(4))
anchor='      layer_tree->AddChild(blur_layer_);'
add(BLUR,anchor,anchor+layer('web_contents()','navigation_id_','blur_layer_.get()',0,'delegate->GetTopControlsHeight()','native_view',0))
# Predictive navigation: selection, intent, tracked request, state, completion.
anchor='  SetupForScreenshotPreview(std::move(embedder_content), first_gesture);'
add(BACK,anchor,anchor+back(0,'static_cast<int>(nav_direction_)'))
for name,stage in [('OnGestureCancelled',1),('OnGestureInvoked',2),('OnContentForNavigationEntryShown',3),('OnPostNavigationFirstFrameTimeout',4),('PostNavigationFirstFrameActivated',5)]:
 anchor='void BackForwardTransitionAnimator::'+name+'() {'
 add(BACK,anchor,anchor+back(stage))
anchor='''  SerializeNavigationRequest(created_request.get());'''
add(BACK,anchor,anchor+back(6,'created_request->IsInPrimaryMainFrame()'))
anchor='  abort_reason_ = abort_reason;'
add(BACK,anchor,anchor+back(7,'static_cast<int>(abort_reason)'))
anchor='  state_ = state;'
add(BACK,anchor,anchor+back(8))
# Accepted activation must be distinct from timeout invoking the common completion helper.
anchor='''  PostNavigationFirstFrameActivated();
}

// We only use `DidStartNavigation()`'''
add(BACK,anchor,back(9,time='activation_time')+anchor)
anchor='''    // We shouldn't dismiss the screenshot if the activated frame isn't what we
    // are expecting.'''
add(BACK,anchor,back(10,time='activation_time')+anchor)
anchor='  parent_layer->InsertChild(screenshot_layer_.get(), screenshot_index);'
add(BACK,anchor,anchor+layer(WC,NAV,'screenshot_layer_.get()',1,'animation_manager_->web_contents_view_android()->GetTopControlsHeight()','animation_manager_->web_contents_view_android()->GetNativeView()',3))

anchor='    pixels->SetPosition(gfx::PointF(0.f, -delegate->GetTopControlsHeight()));'
add(BLUR,anchor,anchor+layer('web_contents()','navigation_handle->GetNavigationId()','pixels.get()',2,'delegate->GetTopControlsHeight()','native_view',1))
anchor='    parent_layer->InsertChild(embedder_live_content_clone_.get(),\n                              web_page_widgets_index + 1);'
add(BACK,anchor,anchor+layer(WC,NAV,'embedder_live_content_clone_.get()',3,'animation_manager_->web_contents_view_android()->GetTopControlsHeight()','animation_manager_->web_contents_view_android()->GetNativeView()',4))

def transform(path,text):
 for name,old,new in CHANGES:
  if path!=name:continue
  if text.count(new)==1 and old not in text.replace(new,'',1):continue
  if text.count(old)!=1 or new in text:raise ValueError('Unknown diagnostic anchor: '+name+' '+old[:70])
  text=text.replace(old,new,1)
 return text

def plan(root):
 root=Path(root)
 return {root/name:transform(name,(root/name).read_text()) for name in (BLUR,BACK)}
