#!/usr/bin/env python3
"""Inverse-dependency capture observer; UI recorder supplies optional callback."""
PATH='chrome/browser/gesturenav/android/java/src/org/chromium/chrome/browser/gesturenav/NativePageBitmapCapturer.java'
HELPER='''
    // SANDIUM_CAPTURE_RING_V1: optional UI-owned numeric sink, not a module dependency.
    public interface SandiumOriginObserver {
        boolean isEnabled(Tab tab);
        void record(Tab tab, double[] values);
        void matrix(Tab tab, double[] values);
    }
    private static volatile @Nullable SandiumOriginObserver sSandiumOriginObserver;
    private static long sSandiumCaptureSample;
    public static void setSandiumOriginObserver(@Nullable SandiumOriginObserver observer) {
        sSandiumOriginObserver = observer;
    }
    private static void sandiumCaptureOrigin(Tab tab, int stage, int topHeight) {
        SandiumOriginObserver observer = sSandiumOriginObserver;
        if (observer == null || android.os.Looper.myLooper() != android.os.Looper.getMainLooper()) return;
        try {
            if (!observer.isEnabled(tab)) return;
            View root = tab.getView();
            var page = tab.getNativePage();
            var contents = tab.getWebContents();
            if (root == null || page == null || contents == null) return;
            var delegate = contents.getViewAndroidDelegate();
            if (delegate == null) return;
            View web = delegate.getContainerView();
            if (web == null) return;
            int[] nativeWindow = new int[2];
            int[] webWindow = new int[2];
            root.getLocationInWindow(nativeWindow);
            web.getLocationInWindow(webWindow);
            long sample = ++sSandiumCaptureSample;
            observer.record(tab, new double[] {sample, stage, nativeWindow[0], nativeWindow[1],
                    webWindow[0], webWindow[1], root.getWidth(), root.getHeight(),
                    web.getWidth(), web.getHeight(), page.getHeightOverlappedWithTopControls(),
                    topHeight, root.isAttachedToWindow() ? 1 : 0,
                    web.isAttachedToWindow() ? 1 : 0, root.getScrollY(), web.getScrollY()});
            float[] values = new float[9];
            root.getMatrix().getValues(values);
            observer.matrix(tab, new double[] {sample, 0, values[0], values[1], values[2],
                    values[3], values[4], values[5], values[6], values[7], values[8]});
            web.getMatrix().getValues(values);
            observer.matrix(tab, new double[] {sample, 1, values[0], values[1], values[2],
                    values[3], values[4], values[5], values[6], values[7], values[8]});
        } catch (RuntimeException ignored) {
            // Optional diagnostics must never affect native page capture or navigation.
        }
    }
'''
def once(s,old,new):
 if new in s:return s
 if s.count(old)!=1:raise ValueError('Capture diagnostic anchor drift: '+old[:80])
 return s.replace(old,new,1)
def transform(s):
 s=once(s,'public class NativePageBitmapCapturer {','public class NativePageBitmapCapturer {'+HELPER)
 s=once(s,'public void onCaptureStart(Canvas canvas, Rect dirtyRect) {','public void onCaptureStart(Canvas canvas, Rect dirtyRect) {\n                            sandiumCaptureOrigin(tab, 1, 0);')
 s=once(s,'            Canvas canvas = new Canvas(bitmap);','            sandiumCaptureOrigin(tab, fullscreen ? 2 : 3, topControlsHeight);\n            Canvas canvas = new Canvas(bitmap);')
 return s
