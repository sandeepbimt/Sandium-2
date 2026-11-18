"""Dormant unwrapped-NTP capture origin contract; no layout or margin changes."""
from pathlib import Path
PAGE='chrome/browser/ui/android/native_page/java/src/org/chromium/chrome/browser/ui/native_page/NativePage.java'
NTP='chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPage.java'
CAPTURE='chrome/browser/gesturenav/android/java/src/org/chromium/chrome/browser/gesturenav/NativePageBitmapCapturer.java'
API='''    /** Capture-only normalization; null preserves Chromium's existing overlap contract. */
    default @Nullable Integer getSandiumCaptureTopOverlap() { return null; }

'''
OWNER='''    // SANDIUM_UNWRAPPED_NTP_CAPTURE_V1
    @Override
    public @Nullable Integer getSandiumCaptureTopOverlap() {
        if (mIsDestroyed || mTab.getNativePage() != this || mTab.isIncognitoBranded()) return null;
        // A wallpaper wrapper already contains the foreground margin in local pixels.
        // Applying the unwrapped-root invariant there would subtract that margin twice.
        if (mFeedSurfaceProvider instanceof FeedSurfaceCoordinator
                && ((FeedSurfaceCoordinator) mFeedSurfaceProvider).hasSandiumWallpaperRoot()) return null;
        View view = getView();
        if (view == null || !view.isAttachedToWindow() || view.isLayoutRequested()
                || view.getWidth() <= 0 || view.getHeight() <= 0
                || !view.getMatrix().isIdentity() || view.getScrollX() != 0 || view.getScrollY() != 0
                || !(view.getParent() instanceof ViewGroup)) return null;
        ViewGroup parent = (ViewGroup) view.getParent();
        if (!parent.isAttachedToWindow() || parent.isLayoutRequested()
                || !parent.getMatrix().isIdentity() || parent.getPaddingTop() != 0
                || parent.getPaddingLeft() != 0 || parent.getScrollX() != 0 || parent.getScrollY() != 0
                || !(view.getLayoutParams() instanceof ViewGroup.MarginLayoutParams)) return null;
        ViewGroup.MarginLayoutParams params = (ViewGroup.MarginLayoutParams) view.getLayoutParams();
        int strip = mTabStripHeightSupplier.get();
        if (mToolbarHeight < 0 || strip < 0 || mToolbarHeight > Integer.MAX_VALUE - strip) return null;
        int overlap = mToolbarHeight + strip;
        int contentOffset = mBrowserControlsStateProvider.getContentOffset();
        // Restrict to the measured settled bottom-toolbar route. No new assumptions about
        // dynamic top-controls/Viz offsets, tablet strips or moving toolbar geometry.
        if (mToolbarHeight <= 0 || strip != 0 || contentOffset != 0
                || mBrowserControlsStateProvider.getTopControlsHeight() != 0
                || mBrowserControlsStateProvider.getTopControlOffset() != 0
                || mBrowserControlsStateProvider.getBottomControlOffset() != 0
                || mBrowserControlsStateProvider.getBottomControlsHeight() < mToolbarHeight) return null;
        // updateMargins sets root top = contentOffset - toolbarHeight - tabStripHeight.
        // Native StaticTabSceneLayer places the content parent at contentOffset (physical px).
        if (params.topMargin != contentOffset - overlap || view.getTop() != params.topMargin
                || params.leftMargin != 0 || view.getLeft() != 0) return null;
        return overlap;
    }

'''
HELPER='''    // SANDIUM_NATIVE_CAPTURE_ORIGIN_V1
'''
SNAPSHOT='''    private static final class SandiumCaptureSnapshot {
        final NativePage page;
        final View view;
        final org.chromium.content_public.browser.WebContents contents;
        final View container;
        final int viewportWidth, viewportHeight;
        final boolean attached;
        final int[] windowLocation = new int[2];
        final int overlap, background, width, height, top, left, scrollX, scrollY;
        final @Nullable Object parent;
        final @Nullable Integer ownedOverlap;
        final android.graphics.Matrix matrix;
        SandiumCaptureSnapshot(Tab tab) {
            page = assumeNonNull(tab.getNativePage());
            view = assumeNonNull(tab.getView());
            contents = assumeNonNull(tab.getWebContents());
            container = assumeNonNull(assumeNonNull(contents.getViewAndroidDelegate()).getContainerView());
            viewportWidth = container.getWidth(); viewportHeight = container.getHeight();
            ownedOverlap = page.getSandiumCaptureTopOverlap();
            overlap = ownedOverlap != null ? ownedOverlap : page.getHeightOverlappedWithTopControls();
            background = page.getBackgroundColor();
            width = view.getWidth(); height = view.getHeight();
            top = view.getTop(); left = view.getLeft();
            scrollX = view.getScrollX(); scrollY = view.getScrollY();
            parent = view.getParent();
            attached = view.isAttachedToWindow();
            view.getLocationInWindow(windowLocation);
            matrix = new android.graphics.Matrix(view.getMatrix());
        }
        boolean matchesRecording(Tab tab) {
            int[] currentLocation = new int[2];
            view.getLocationInWindow(currentLocation);
            return tab.getNativePage() == page && tab.getView() == view
                    && tab.getWebContents() == contents && !contents.isDestroyed()
                    && contents.getViewAndroidDelegate() != null
                    && contents.getViewAndroidDelegate().getContainerView() == container
                    && container.getWidth() == viewportWidth && container.getHeight() == viewportHeight
                    && view.getParent() == parent && view.isAttachedToWindow() == attached
                    && java.util.Arrays.equals(currentLocation, windowLocation)
                    && view.getWidth() == width && view.getHeight() == height
                    && view.getTop() == top && view.getLeft() == left
                    && view.getScrollX() == scrollX && view.getScrollY() == scrollY
                    && matrix.equals(view.getMatrix())
                    && java.util.Objects.equals(ownedOverlap, page.getSandiumCaptureTopOverlap());
        }
    }

    private static void discardSandiumCapture(@Nullable CaptureResult result, int destination) {
        if (result == null) return;
        if (destination == CaptureResult.Destination.HARDWARE_BUFFER) {
            try {
                result.getHardwareBuffer().close();
            } finally {
                result.getReleaseCallback().run();
            }
        } else {
            result.getBitmap().recycle();
        }
    }

'''
def once(s,a,b):
 if s.count(a)!=1:raise ValueError('Capture coordinate anchor drift: '+a[:90])
 return s.replace(a,b,1)
def transform(path,s):
 if path==PAGE:
  if API in s:return s
  if 'getSandiumCaptureTopOverlap' in s:raise ValueError('Partial capture API')
  return once(s,'    default int getHeightOverlappedWithTopControls() {',API+'    default int getHeightOverlappedWithTopControls() {')
 if path==NTP:
  if OWNER in s:return s
  if 'SANDIUM_UNWRAPPED_NTP_CAPTURE' in s:raise ValueError('Partial capture owner')
  return once(s,'    @Override\n    public int getHeightOverlappedWithTopControls() {',OWNER+'    @Override\n    public int getHeightOverlappedWithTopControls() {')
 if path==CAPTURE:
  if HELPER in s:
   required=('recordingValid[0] &= snapshot.matchesRecording(tab);',
             'discardSandiumCapture(resultCapture, destination);',
             'bitmap == null ? null : new CaptureResult(bitmap)',
             'canvas.translate(0, -snapshot.overlap);')
   if SNAPSHOT not in s or s.count('new SandiumCaptureSnapshot(tab)')!=2 or s.count('snapshot.viewportHeight')!=2 or any(s.count(x)!=1 for x in required):
    raise ValueError('Partial capture consumers')
   return s
  if 'SANDIUM_NATIVE_CAPTURE_ORIGIN' in s:raise ValueError('Partial capture helper')
  s=once(s,'    private static final float SCALE = 1;',HELPER+SNAPSHOT+'    private static final float SCALE = 1;')
  s=once(s,'            return capturer.mHardwareDraw.startBitmapCapture(\n                    assumeNonNull(tab.getView()),',
   '            final SandiumCaptureSnapshot snapshot = new SandiumCaptureSnapshot(tab);\n            final boolean[] recordingValid = {true};\n            return capturer.mHardwareDraw.startBitmapCapture(\n                    snapshot.view,')
  s=once(s,'                    tab.getWebContents().getViewAndroidDelegate().getContainerView().getHeight(),','                    snapshot.viewportHeight,')
  s=once(s,'''                            assumeNonNull(tab.getNativePage());
                            canvas.drawColor(tab.getNativePage().getBackgroundColor());
                            canvas.translate(
                                    0, -tab.getNativePage().getHeightOverlappedWithTopControls());''','''                            recordingValid[0] = snapshot.matchesRecording(tab);
                            if (!recordingValid[0]) {
                                canvas.clipRect(0, 0, 0, 0);
                                return;
                            }
                            canvas.drawColor(snapshot.background);
                            canvas.translate(0, -snapshot.overlap);''')
  s=once(s,'                        public void onCaptureEnd() {}','''                        public void onCaptureEnd() {
                            recordingValid[0] &= snapshot.matchesRecording(tab);
                        }''')
  s=once(s,'                    callback,\n                    destination);','''                    resultCapture -> {
                        // Capture recorded synchronously; later ordinary page departure is valid.
                        // Never substitute the new current page for this immutable recording.
                        if (!recordingValid[0]) {
                            try {
                                discardSandiumCapture(resultCapture, destination);
                            } finally {
                                callback.onResult(null);
                            }
                            return;
                        }
                        callback.onResult(resultCapture);
                    },
                    destination);''')
  s=once(s,'            Bitmap bitmap = capture(tab, false, 0);','            @Nullable Bitmap bitmap = capture(tab, false, 0);')
  s=once(s,'TaskTraits.UI_USER_VISIBLE, () -> callback.onResult(new CaptureResult(bitmap)));',
   'TaskTraits.UI_USER_VISIBLE, () -> callback.onResult(bitmap == null ? null : new CaptureResult(bitmap)));')
  s=once(s,'    private static Bitmap capture(Tab tab, boolean fullscreen, int topControlsHeight) {',
   '    private static @Nullable Bitmap capture(Tab tab, boolean fullscreen, int topControlsHeight) {')
  s=once(s,'            View view = assumeNonNull(tab.getView());',
   '            final SandiumCaptureSnapshot snapshot = new SandiumCaptureSnapshot(tab);\n            View view = snapshot.view;')
  s=once(s,'''                            view.getWidth(),
                            tab.getWebContents()
                                    .getViewAndroidDelegate()
                                    .getContainerView()
                                    .getHeight());''',
   '                            snapshot.width, snapshot.viewportHeight);')
  s=once(s,'            bitmap.eraseColor(assumeNonNull(tab.getNativePage()).getBackgroundColor());',
   '            bitmap.eraseColor(snapshot.background);')
  s=once(s,'-tab.getNativePage().getHeightOverlappedWithTopControls()','-snapshot.overlap')
  s=once(s,'            view.draw(canvas);\n            return bitmap;','''            view.draw(canvas);
            if (!snapshot.matchesRecording(tab)) {
                bitmap.recycle();
                return null;
            }
            return bitmap;''')
  return s
 raise ValueError(path)
def plan(root):
 root=Path(root)
 return {root/p:transform(p,(root/p).read_text()) for p in (PAGE,NTP,CAPTURE)}
