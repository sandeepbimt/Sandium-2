"""Dormant root UI visibility gate. Pure query, not universal occlusion proof."""
from pathlib import Path
PATH = "chrome/android/java/src/org/chromium/chrome/browser/ui/RootUiCoordinator.java"
MARKER = "SANDIUM_NATIVE_HANDOFF_ROOT_GATE_V1"
FIELD = "    // SANDIUM_NATIVE_HANDOFF_ROOT_GATE_V1\n    private boolean mSandiumNativeHandoffUiDestroyed;\n"
METHOD = """    /** Conservative live predicate; holder still owns geometry, input and lifetime gates. */
    public boolean isSandiumNativeHandoffUiClear() {
        org.chromium.base.ThreadUtils.assertOnUiThread();
        if (mSandiumNativeHandoffUiDestroyed || mActivity.isFinishing()
                || mActivity.isDestroyed()) return false;
        var obscuring = mTabObscuringHandlerSupplier.get();
        var modal = mModalDialogManagerSupplier.get();
        var sheet = mBottomSheetControllerSupplier.get();
        var scrim = mScrimManagerSupplier.get();
        var menu = mAppMenuCoordinator;
        if (obscuring == null || modal == null || sheet == null || scrim == null || menu == null) {
            return false; // Not initialized or unknown is not clear.
        }
        int target = sheet.getTargetSheetState();
        boolean clear = !obscuring.isTabContentObscured() && !obscuring.isToolbarObscured()
                && !modal.isShowing() && sheet.getSheetState() == SheetState.HIDDEN
                && (target == SheetState.HIDDEN || target == SheetState.NONE)
                && !sheet.isSheetHiding()
                && Boolean.FALSE.equals(scrim.getScrimVisibilitySupplier().get())
                && !menu.getAppMenuHandler().isAppMenuShowing();
        // Read accessors above must not authorize a torn-down/replaced root owner.
        boolean identities = obscuring == mTabObscuringHandlerSupplier.get()
                && modal == mModalDialogManagerSupplier.get()
                && sheet == mBottomSheetControllerSupplier.get()
                && scrim == mScrimManagerSupplier.get() && menu == mAppMenuCoordinator;
        return clear && identities && !mSandiumNativeHandoffUiDestroyed
                && !mActivity.isFinishing() && !mActivity.isDestroyed();
    }

"""

def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Pinned root UI anchor drift: " + old[:80])
    return text.replace(old, new, 1)

def transform(text):
    if MARKER in text:
        if text.count(MARKER) != 1 or FIELD not in text or METHOD not in text or                 '    public void onDestroy() {\n        mSandiumNativeHandoffUiDestroyed = true;' not in text:
            raise ValueError("Partial root UI handoff gate")
        return text
    text = once(text, '    protected AppCompatActivity mActivity;\n', FIELD + '    protected AppCompatActivity mActivity;\n')
    anchor = '    @Override\n    @SuppressWarnings("NullAway")\n    public void onDestroy() {'
    text = once(text, anchor, METHOD + anchor)
    return once(text, '    public void onDestroy() {\n', '    public void onDestroy() {\n        mSandiumNativeHandoffUiDestroyed = true;\n')

def plan(root):
    path = Path(root) / PATH
    return {path: transform(path.read_text())}
