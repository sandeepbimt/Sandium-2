"""Dormant no-reparent native-home lease; requires offer, safety and adapter stages."""
from pathlib import Path
PATH='chrome/android/java/src/org/chromium/chrome/browser/compositor/CompositorViewHolder.java'
MARKER='SANDIUM_NATIVE_HOME_RETAIN_V1'
FIELDS='''    // SANDIUM_NATIVE_HOME_RETAIN_V1
    private org.chromium.chrome.browser.tab.NativePageHandoffOffer.@Nullable Claim mSandiumRetained;
    private long mSandiumRetainedToken;
    private long mSandiumNextRetainedToken;
    private long mSandiumRetainedDeadline;
    private @Nullable Runnable mSandiumRetainedExpiry;
    private int mSandiumRetainedA11y;
    private int mSandiumRetainedFocusability;
    private @Nullable int[] mSandiumRetainedGeometry;
    private boolean mSandiumRetainedStarted;
    private int mSandiumReleaseDepth;
    private boolean mSandiumConsumeTouch;
    private boolean mSandiumConsumeDrag;
    private final java.util.HashSet<Integer> mSandiumConsumeKeys = new java.util.HashSet<>();

'''
METHODS='''    private int[] sandiumGeometry(View view) {
        int[] location = new int[2];
        view.getLocationInWindow(location);
        return new int[] {getWidth(), getHeight(), view.getLeft(), view.getTop(),
                view.getWidth(), view.getHeight(), location[0], location[1]};
    }

    private boolean sandiumHolderLocallySafe() {
        return isAttachedToWindow() && hasWindowFocus() && isShown()
                && !mInTouch && !mInGesture
                && !mContentViewScrolling && !mIsKeyboardShowing && mContentOverlayVisiblity
                && (mUrlBar == null || !mUrlBar.hasFocus())
                && isSandiumNativeHandoffUiSafe();
    }

    private void offerSandiumNativeHome(Tab tab,
            org.chromium.chrome.browser.tab.NativePageHandoffOffer offer) {
        @Nullable View outgoing = mView;
        if (outgoing == null) return;
        if (mSandiumReleaseDepth != 0 || mSandiumRetained != null || tab != mTabVisible || mView == null
                || mView.getParent() != this || isLayoutRequested() || !sandiumHolderLocallySafe()
                || mSandiumReleaseDepth != 0 || mSandiumRetained != null || mView != outgoing || mTabVisible != tab
                || mView.getVisibility() != View.VISIBLE || mView.getAlpha() != 1f
                || mView.getAnimation() != null || mView.hasTransientState()
                || mView.isLayoutRequested() || mView.getWidth() <= 0 || mView.getHeight() <= 0
                || (mView.findFocus() != null && mView.findFocus() != mView)
                || !(mView instanceof ViewGroup)
                || mSandiumNextRetainedToken == Long.MAX_VALUE) return;
        // No unknown visible holder overlays. The existing compositor and native root are allowed.
        for (int i = 0; i < getChildCount(); ++i) {
            View child = getChildAt(i);
            if (child != mView && child != mCompositorView && child.getVisibility() == View.VISIBLE) return;
        }
        org.chromium.chrome.browser.tab.NativePageHandoffOffer.@Nullable Claim claim =
                offer.claim(tab, mView);
        if (claim == null) return;
        View retained = claim.view();
        mSandiumRetained = claim;
        mSandiumRetainedToken = ++mSandiumNextRetainedToken;
        final long token = mSandiumRetainedToken;
        mSandiumRetainedDeadline = android.os.SystemClock.uptimeMillis() + 500;
        mSandiumRetainedGeometry = sandiumGeometry(retained);
        mSandiumRetainedA11y = retained.getImportantForAccessibility();
        mSandiumRetainedFocusability = ((ViewGroup) retained).getDescendantFocusability();
        mSandiumUnsafeCallback = () -> releaseSandiumNativeHome(token);
        final Runnable expiry = () -> releaseSandiumNativeHome(token);
        mSandiumRetainedExpiry = expiry;
        if (!postDelayed(expiry, Math.max(0L,
                mSandiumRetainedDeadline - android.os.SystemClock.uptimeMillis()))) {
            releaseSandiumNativeHome(token);
            return;
        }
        try {
            retained.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
            if (claim != mSandiumRetained || token != mSandiumRetainedToken) return;
            ((ViewGroup) retained).setDescendantFocusability(ViewGroup.FOCUS_BLOCK_DESCENDANTS);
            if (claim != mSandiumRetained || token != mSandiumRetainedToken) return;
            retained.clearFocus();
            if (claim != mSandiumRetained || token != mSandiumRetainedToken) return;
        } catch (RuntimeException | Error error) {
            releaseSandiumNativeHome(token);
            throw error;
        }
    }

    private boolean sandiumRetainedEligible(long token) {
        org.chromium.chrome.browser.tab.NativePageHandoffOffer.@Nullable Claim claim = mSandiumRetained;
        if (claim == null || token != mSandiumRetainedToken || isLayoutRequested() || !claim.isValid()
                || android.os.SystemClock.uptimeMillis() >= mSandiumRetainedDeadline
                || !sandiumHolderLocallySafe()) return false;
        if (claim != mSandiumRetained || token != mSandiumRetainedToken || !claim.isValid()) return false;
        // Reject newly appearing native siblings too, not only overlays present at acquisition.
        for (int i = 0; i < getChildCount(); ++i) {
            View child = getChildAt(i);
            if (child != claim.view() && child != mCompositorView && child != mView
                    && child.getVisibility() == View.VISIBLE) return false;
        }
        // Pure identity/geometry recheck after the externally supplied policy.
        return claim == mSandiumRetained && token == mSandiumRetainedToken
                && claim.isValid() && mTabVisible == claim.tab()
                && mView != null && mView != claim.view() && mView == claim.tab().getView()
                && mView.getParent() == this
                && claim.tab().getWebContents() == claim.contents()
                && claim.view().getParent() == this
                && claim.view().getVisibility() == View.VISIBLE && claim.view().getAlpha() == 1f
                && claim.view().getAnimation() == null && !claim.view().hasTransientState()
                && !claim.view().isLayoutRequested()
                && java.util.Arrays.equals(mSandiumRetainedGeometry, sandiumGeometry(claim.view()));
    }

    private void startSandiumNativeHome() {
        org.chromium.chrome.browser.tab.NativePageHandoffOffer.@Nullable Claim claim = mSandiumRetained;
        if (claim == null || mSandiumRetainedStarted) return;
        // addView(destination) normally requests layout. Wait for the normal draw traversal,
        // within the original absolute lease budget, rather than treating that as readiness.
        if (isLayoutRequested()) return;
        final long token = mSandiumRetainedToken;
        if (!sandiumRetainedEligible(token) || mView == claim.view()
                || mTabVisible != claim.tab() || mLayoutManager == null) {
            releaseSandiumNativeHome(token);
            return;
        }
        mSandiumRetainedStarted = true;
        try {
            if (!mCompositorView.beginSandiumNativeHandoff(token, claim.tab(), claim.contents(),
                    mLayoutManager, () -> sandiumRetainedEligible(token),
                    presented -> releaseSandiumNativeHome(token))) releaseSandiumNativeHome(token);
        } catch (RuntimeException | Error error) {
            releaseSandiumNativeHome(token);
            throw error;
        }
    }

    private void releaseSandiumNativeHome(long token) {
        if (token == 0 || token != mSandiumRetainedToken) return;
        org.chromium.chrome.browser.tab.NativePageHandoffOffer.@Nullable Claim claim = mSandiumRetained;
        @Nullable Runnable expiry = mSandiumRetainedExpiry;
        int a11y = mSandiumRetainedA11y;
        int focusability = mSandiumRetainedFocusability;
        mSandiumRetained = null;
        mSandiumRetainedToken = 0;
        mSandiumRetainedExpiry = null;
        mSandiumRetainedGeometry = null;
        mSandiumRetainedStarted = false;
        mSandiumUnsafeCallback = null;
        if (expiry != null) removeCallbacks(expiry);
        // Dispose the old view BEFORE cancel can reenter and offer the same cached native page.
        // All ownership fields are already clear; the final cancel is scoped to the old token.
        ++mSandiumReleaseDepth;
        try {
            if (claim != null) {
                try {
                    View retained = claim.view();
                    retained.setImportantForAccessibility(a11y);
                    ((ViewGroup) retained).setDescendantFocusability(focusability);
                    if (retained.getParent() == this && claim.tab().getNativePage() != claim.page()) {
                        removeView(retained);
                    }
                } finally {
                    claim.close();
                }
            }
        } finally {
            try {
                mCompositorView.cancelSandiumNativeHandoff(token);
            } finally {
                --mSandiumReleaseDepth;
            }
        }
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        if (!hasFocus) releaseSandiumNativeHome(mSandiumRetainedToken);
        super.onWindowFocusChanged(hasFocus);
    }

    @Override
    protected void dispatchDraw(android.graphics.Canvas canvas) {
        startSandiumNativeHome();
        long token = mSandiumRetainedToken;
        if (token != 0 && !sandiumRetainedEligible(token)) releaseSandiumNativeHome(token);
        super.dispatchDraw(canvas);
    }

'''
def once(s,a,b):
 if s.count(a)!=1:raise ValueError('Retained holder anchor drift: '+a[:90])
 return s.replace(a,b,1)
def transform(s):
 if MARKER in s:
  required=('offerSandiumNativeHome(tab, offer);',
            'if (!show && mSandiumRetained != null && mView == mSandiumRetained.view()) return;',
            'mSandiumConsumeKeys.add(event.getKeyCode());',
            'if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL)',
            'if (!show) releaseSandiumNativeHome(mSandiumRetainedToken);')
  if FIELDS not in s or METHODS not in s or any(s.count(x)!=1 for x in required):
   raise ValueError('Partial retained holder')
  return s
 s=once(s,'    private static final long SYSTEM_UI_VIEWPORT_UPDATE_DELAY_MS = 500;',FIELDS+METHODS+'    private static final long SYSTEM_UI_VIEWPORT_UPDATE_DELAY_MS = 500;')
 s=once(s,'                public void onContentChanged(Tab tab) {','''                public void onNativePageHandoffOffered(Tab tab,
                        org.chromium.chrome.browser.tab.NativePageHandoffOffer offer) {
                    offerSandiumNativeHome(tab, offer);
                }

                @Override
                public void onContentChanged(Tab tab) {''')
 s=once(s,'        if (mView == null) return;\n        WebContents webContents = getWebContents();','''        if (mView == null) return;
        if (!show && mSandiumRetained != null && mView == mSandiumRetained.view()) return;
        WebContents webContents = getWebContents();''')
 s=once(s,'        // Clear drop permissions when tab changes unless this is a new tab loading from the drop.','''        startSandiumNativeHome();

        // Clear drop permissions when tab changes unless this is a new tab loading from the drop.''')
 s=once(s,'    private void setTab(@Nullable Tab tab) {','''    private void setTab(@Nullable Tab tab) {
        if (mSandiumRetained != null && tab != mSandiumRetained.tab()) {
            releaseSandiumNativeHome(mSandiumRetainedToken);
        }''')
 s=once(s,'    public boolean dispatchTouchEvent(MotionEvent e) {','''    public boolean dispatchTouchEvent(MotionEvent e) {
        if (mSandiumRetainedToken != 0) {
            mSandiumConsumeTouch = true;
            releaseSandiumNativeHome(mSandiumRetainedToken);
        }
        if (mSandiumConsumeTouch) {
            int action = e.getActionMasked();
            if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL) {
                mSandiumConsumeTouch = false;
            }
            return true;
        }''')
 # Gate content inputs before superclass, and consume matching sequence tails.
 for anchor in ('    public boolean dispatchGenericMotionEvent(MotionEvent e) {',
                '    public boolean dispatchHoverEvent(MotionEvent e) {'):
  s=once(s,anchor,anchor+"\n        if (mSandiumRetainedToken != 0) {\n            releaseSandiumNativeHome(mSandiumRetainedToken);\n            return true;\n        }")
 s=once(s,'    public boolean dispatchDragEvent(DragEvent e) {','''    public boolean dispatchDragEvent(DragEvent e) {
        if (mSandiumRetainedToken != 0) {
            mSandiumConsumeDrag = true;
            releaseSandiumNativeHome(mSandiumRetainedToken);
        }
        if (mSandiumConsumeDrag) {
            if (e.getAction() == DragEvent.ACTION_DRAG_ENDED) mSandiumConsumeDrag = false;
            return true;
        }''')
 s=once(s,'    public boolean dispatchKeyEvent(KeyEvent event) {','''    public boolean dispatchKeyEvent(KeyEvent event) {
        boolean sandiumCancelKey = event.getKeyCode() == KeyEvent.KEYCODE_BACK
                || event.getKeyCode() == KeyEvent.KEYCODE_ESCAPE;
        if (mSandiumRetainedToken != 0) {
            if (!sandiumCancelKey) mSandiumConsumeKeys.add(event.getKeyCode());
            releaseSandiumNativeHome(mSandiumRetainedToken);
        }
        if (!sandiumCancelKey && mSandiumConsumeKeys.contains(event.getKeyCode())) {
            if (event.getAction() == KeyEvent.ACTION_UP) mSandiumConsumeKeys.remove(event.getKeyCode());
            return true;
        }''')
 for anchor in ('    public void shutDown() {','    public void onDetachedFromWindow() {',
                '    public void onStop() {'):
  s=once(s,anchor,anchor+'\n        releaseSandiumNativeHome(mSandiumRetainedToken);\n        mSandiumConsumeTouch = false;\n        mSandiumConsumeDrag = false;\n        mSandiumConsumeKeys.clear();')
 for anchor in ('    public void onTopControlsHeightChanged(int topControlsHeight, int topControlsMinHeight) {',
                '            int bottomControlsHeight, int bottomControlsMinHeight) {',
                '            boolean isVisibilityForced) {'):
  s=once(s,anchor,anchor+'\n        releaseSandiumNativeHome(mSandiumRetainedToken);')
 s=once(s,'    public void setContentOverlayVisibility(boolean show, boolean canBeFocusable) {',
        '    public void setContentOverlayVisibility(boolean show, boolean canBeFocusable) {\n        if (!show) releaseSandiumNativeHome(mSandiumRetainedToken);')
 s=once(s,'    protected void onSizeChanged(int w, int h, int oldw, int oldh) {',
        '    protected void onSizeChanged(int w, int h, int oldw, int oldh) {\n        releaseSandiumNativeHome(mSandiumRetainedToken);')
 s=once(s,'    protected void onLayout(boolean changed, int l, int t, int r, int b) {','''    protected void onLayout(boolean changed, int l, int t, int r, int b) {
        if (changed) releaseSandiumNativeHome(mSandiumRetainedToken);''')
 return s
def plan(root):
 p=Path(root)/PATH
 return {p:transform(p.read_text())}
