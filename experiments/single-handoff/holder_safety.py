"""Dormant holder safety subscription. No presentation or retention policy here."""
from pathlib import Path
HOLDER='chrome/android/java/src/org/chromium/chrome/browser/compositor/CompositorViewHolder.java'
ACTIVITY='chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java'
MARKER='SANDIUM_NATIVE_HANDOFF_SAFETY_V1'
FIELDS='''    // SANDIUM_NATIVE_HANDOFF_SAFETY_V1
    private boolean mSandiumSafetyClosed;
    private boolean mSandiumA11yKnown;
    private boolean mSandiumA11yEnabled;
    private boolean mSandiumObscuringKnown;
    private boolean mSandiumObscured;
    private java.util.function.@Nullable BooleanSupplier mSandiumUiSafety;
    private @Nullable Runnable mSandiumUnsafeCallback;
    private boolean mSandiumA11yRegistered;
    private final AccessibilityUtil.Observer mSandiumSafetyA11yObserver = enabled -> {
        mSandiumA11yKnown = true;
        mSandiumA11yEnabled = enabled;
        if (enabled) notifySandiumUnsafe();
    };

'''
METHODS='''    /** Separate observer: never enables the tablet-only virtual accessibility provider. */
    public void installSandiumNativeHandoffSafety(java.util.function.BooleanSupplier policy) {
        org.chromium.base.ThreadUtils.assertOnUiThread();
        if (mSandiumSafetyClosed) return;
        mSandiumUiSafety = policy;
        if (!mSandiumA11yRegistered) {
            mSandiumA11yRegistered = true;
            // The pinned utility seeds this observer synchronously for phones AND tablets.
            org.chromium.chrome.browser.util.ChromeAccessibilityUtil.get()
                    .addObserver(mSandiumSafetyA11yObserver);
        }
        if (!isSandiumNativeHandoffUiSafe()) notifySandiumUnsafe();
    }

    private boolean isSandiumNativeHandoffUiSafe() {
        java.util.function.@Nullable BooleanSupplier policy = mSandiumUiSafety;
        if (mSandiumSafetyClosed || !mSandiumA11yKnown || mSandiumA11yEnabled
                || !mSandiumObscuringKnown || mSandiumObscured || policy == null) return false;
        boolean safe = policy.getAsBoolean();
        // The policy may reenter teardown/obscuring. Never return its stale true value.
        return safe && policy == mSandiumUiSafety && !mSandiumSafetyClosed
                && mSandiumA11yKnown && !mSandiumA11yEnabled
                && mSandiumObscuringKnown && !mSandiumObscured;
    }

    private void notifySandiumUnsafe() {
        @Nullable Runnable callback = mSandiumUnsafeCallback;
        if (callback != null) callback.run();
    }

    private void closeSandiumNativeHandoffSafety() {
        mSandiumSafetyClosed = true;
        mSandiumUiSafety = null;
        if (mSandiumA11yRegistered) {
            mSandiumA11yRegistered = false;
            org.chromium.chrome.browser.util.ChromeAccessibilityUtil.get()
                    .removeObserver(mSandiumSafetyA11yObserver);
        }
        @Nullable Runnable callback = mSandiumUnsafeCallback;
        mSandiumUnsafeCallback = null;
        if (callback != null) callback.run();
    }

'''
def once(s,a,b):
    if s.count(a)!=1:raise ValueError('Holder safety anchor drift: '+a[:90])
    return s.replace(a,b,1)
def transform(path,s):
    if path==HOLDER:
        if MARKER in s:
            if (FIELDS not in s or METHODS not in s
                    or s.count('mSandiumObscured = obscureTabContent || obscureToolbar;')!=1
                    or s.count('        closeSandiumNativeHandoffSafety();')!=1):
                raise ValueError('Partial holder safety')
            return s
        s=once(s,'    private static final long SYSTEM_UI_VIEWPORT_UPDATE_DELAY_MS = 500;',FIELDS+METHODS+'    private static final long SYSTEM_UI_VIEWPORT_UPDATE_DELAY_MS = 500;')
        s=once(s,'    public void updateObscured(boolean obscureTabContent, boolean obscureToolbar) {', '''    public void updateObscured(boolean obscureTabContent, boolean obscureToolbar) {
        mSandiumObscuringKnown = true;
        mSandiumObscured = obscureTabContent || obscureToolbar;
        if (mSandiumObscured) notifySandiumUnsafe();''')
        return once(s,'    public void shutDown() {','    public void shutDown() {\n        closeSandiumNativeHandoffSafety();')
    if path==ACTIVITY:
        anchor='            mRootUiCoordinator.getTabObscuringHandler().addObserver(mCompositorViewHolder);'
        replacement=anchor+'''\n            // SANDIUM_NATIVE_HANDOFF_SAFETY_V1: obscuring addObserver does not seed.
            mCompositorViewHolder.updateObscured(
                    mRootUiCoordinator.getTabObscuringHandler().isTabContentObscured(),
                    mRootUiCoordinator.getTabObscuringHandler().isToolbarObscured());
            mCompositorViewHolder.installSandiumNativeHandoffSafety(
                    () -> mRootUiCoordinator != null
                            && mRootUiCoordinator.isSandiumNativeHandoffUiClear());'''
        if MARKER in s:
            if replacement not in s:raise ValueError('Partial CTA safety')
            return s
        return once(s,anchor,replacement)
    raise ValueError(path)
def plan(root):
    root=Path(root)
    return {root/p:transform(p,(root/p).read_text()) for p in (HOLDER,ACTIVITY)}
