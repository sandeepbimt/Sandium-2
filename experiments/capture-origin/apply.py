#!/usr/bin/env python3
"""Opt-in numeric-only capture-origin probes. Not wired into any build."""
from pathlib import Path
JAVA='chrome/browser/gesturenav/android/java/src/org/chromium/chrome/browser/gesturenav/NativePageBitmapCapturer.java'
BLUR='content/browser/navigation_transitions/blur_transition_animation_manager.cc'
BACK='content/browser/navigation_transitions/back_forward_transition_animator.cc'
HELPER='''
    // SANDIUM_CAPTURE_ORIGIN_DIAGNOSTIC_V1: numbers only; no URL, title or pixels.
    private static long sSandiumOriginSample;
    private static long sSandiumOriginStartMs;
    private static void sandiumTraceOrigin(Tab tab, int stage, int syncTopHeight) {
        if (!android.util.Log.isLoggable("SandiumCaptureOrigin", android.util.Log.VERBOSE)) {
            sSandiumOriginSample = 0; sSandiumOriginStartMs = 0; return;
        }
        if (tab.getProfile().isOffTheRecord()) return;
        long now = android.os.SystemClock.uptimeMillis();
        if (sSandiumOriginStartMs == 0) sSandiumOriginStartMs = now;
        if (sSandiumOriginSample >= 256 || now - sSandiumOriginStartMs >= 120000) return;
        View root = tab.getView();
        if (root == null || tab.getNativePage() == null || tab.getWebContents() == null
                || tab.getWebContents().getViewAndroidDelegate() == null) return;
        View web = tab.getWebContents().getViewAndroidDelegate().getContainerView();
        if (web == null) return;
        int[] nativeWindow = new int[2];
        int[] webWindow = new int[2];
        root.getLocationInWindow(nativeWindow);
        web.getLocationInWindow(webWindow);
        android.util.Log.i("SandiumCaptureOrigin", "sample=" + (++sSandiumOriginSample)
                + ",timeMs=" + android.os.SystemClock.uptimeMillis() + ",stage=" + stage
                + ",nativeWindowX=" + nativeWindow[0] + ",nativeWindowY=" + nativeWindow[1]
                + ",webWindowX=" + webWindow[0] + ",webWindowY=" + webWindow[1]
                + ",nativeY=" + root.getY() + ",webY=" + web.getY()
                + ",nativeScrollY=" + root.getScrollY() + ",webScrollY=" + web.getScrollY()
                + ",nativePaddingTop=" + root.getPaddingTop() + ",webPaddingTop=" + web.getPaddingTop()
                + ",nativeMatrix=" + root.getMatrix().toShortString()
                + ",webMatrix=" + web.getMatrix().toShortString()
                + ",nativeH=" + root.getHeight() + ",webH=" + web.getHeight()
                + ",nativeAttached=" + root.isAttachedToWindow()
                + ",webAttached=" + web.isAttachedToWindow()
                + ",overlap=" + tab.getNativePage().getHeightOverlappedWithTopControls()
                + ",syncTopHeight=" + syncTopHeight);
    }
'''
def replace(s, old, new):
    if new in s:return s
    if s.count(old)!=1:raise ValueError('Expected exactly one diagnostic anchor: '+old[:90])
    return s.replace(old,new,1)
def java(s):
    s=replace(s,'public class NativePageBitmapCapturer {','public class NativePageBitmapCapturer {'+HELPER)
    s=replace(s,'public void onCaptureStart(Canvas canvas, Rect dirtyRect) {','public void onCaptureStart(Canvas canvas, Rect dirtyRect) {\n                            sandiumTraceOrigin(tab, 1, 0);')
    s=replace(s,'            Canvas canvas = new Canvas(bitmap);','            sandiumTraceOrigin(tab, fullscreen ? 2 : 3, topControlsHeight);\n            Canvas canvas = new Canvas(bitmap);')
    return s

def layer_probe(expr, event):
    # The ancestry is capped; positions are local, not claimed to be window coordinates.
    return '''\n  {\n    auto* sandium_origin_layer = '''+expr+''';
    for (int depth = 0; sandium_origin_layer && depth < 16; ++depth) {
      TRACE_EVENT_INSTANT("disabled-by-default-sandium.capture_origin", "'''+event+'''",
          "depth", depth, "x", sandium_origin_layer->position().x(),
          "y", sandium_origin_layer->position().y(),
          "transform", sandium_origin_layer->transform().ToString());
      sandium_origin_layer = sandium_origin_layer->parent();
    }
  }\n'''
def blur(s):
    old='      layer_tree->AddChild(blur_layer_);'
    return replace(s,old,old+layer_probe('blur_layer_.get()','SandiumBlurOrigin'))
def back(s):
    old='void BackForwardTransitionAnimator::InsertLayersInOrder() {'
    probe=layer_probe('animation_manager_->web_contents_view_android()->GetNativeView()->GetLayer()', 'SandiumBackParentOrigin')
    return replace(s,old,old+probe)
def plan(src):
    return {src/p: f((src/p).read_text()) for p,f in [(JAVA,java),(BLUR,blur),(BACK,back)]}
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('--apply',action='store_true');a=parser.parse_args()
    output=plan(a.source) # All source validation precedes any write.
    if a.apply:
        for p,text in output.items():p.write_text(text)
    print('Diagnostic source plan valid; shipping activation not configured')
