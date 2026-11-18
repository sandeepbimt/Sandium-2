"""Dormant exact-source CompositorView Java handoff boundary; explicit experimental profile."""
from pathlib import Path
PATH='chrome/android/java/src/org/chromium/chrome/browser/compositor/CompositorView.java'
MARKER='SANDIUM_NATIVE_HANDOFF_JAVA_V1'
FIELDS='''    // SANDIUM_NATIVE_HANDOFF_JAVA_V1
    private long mSandiumHandoffToken;
    private long mSandiumLastHandoffToken;
    private boolean mSandiumHandoffShuttingDown;
    private boolean mSandiumHandoffStarting;
    private boolean mSandiumHandoffBeginViolated;
    private org.chromium.chrome.browser.tab.@Nullable Tab mSandiumHandoffTab;
    private @Nullable WebContents mSandiumHandoffContents;
    private @Nullable LayoutProvider mSandiumHandoffProvider;
    private @Nullable LayoutProvider mSandiumFinalizationProvider;
    private @Nullable SceneLayer mSandiumFinalizedScene;
    private java.util.function.@Nullable BooleanSupplier mSandiumHandoffHolderGate;
    private org.chromium.base.@Nullable Callback<Boolean> mSandiumHandoffCompletion;

'''
METHODS='''    // Caller transfers its native-page lease only when begin returns true.
    // Native begin MUST NOT invoke completion; rejection leaves ownership with caller.
    public boolean beginSandiumNativeHandoff(long token,
            org.chromium.chrome.browser.tab.Tab tab, WebContents contents,
            LayoutProvider provider, java.util.function.BooleanSupplier holderGate,
            org.chromium.base.Callback<Boolean> completion) {
        org.chromium.base.ThreadUtils.assertOnUiThread();
        if (mSandiumHandoffShuttingDown || mNativeCompositorView == 0
                || token <= 0 || token <= mSandiumLastHandoffToken
                || mSandiumHandoffToken != 0 || tab == null || contents == null
                || provider == null || holderGate == null || completion == null
                || tab.isDestroyed() || contents.isDestroyed()
                || tab.getWebContents() != contents) return false;
        mSandiumLastHandoffToken = token;
        mSandiumHandoffToken = token;
        mSandiumHandoffTab = tab;
        mSandiumHandoffContents = contents;
        mSandiumHandoffProvider = provider;
        mSandiumHandoffHolderGate = holderGate;
        mSandiumHandoffCompletion = completion;
        boolean accepted;
        mSandiumHandoffStarting = true;
        mSandiumHandoffBeginViolated = false;
        try {
            accepted = CompositorViewJni.get().beginSandiumNativeHandoff(
                    mNativeCompositorView, token, contents);
        } catch (RuntimeException | Error error) {
            if (mSandiumHandoffToken == token) clearSandiumNativeHandoff();
            throw error;
        } finally {
            mSandiumHandoffStarting = false;
        }
        if (!accepted || mSandiumHandoffBeginViolated || mSandiumHandoffToken != token
                || mSandiumHandoffShuttingDown) {
            if (mSandiumHandoffToken == token) clearSandiumNativeHandoff();
            if (accepted && mNativeCompositorView != 0) {
                CompositorViewJni.get().cancelSandiumNativeHandoff(mNativeCompositorView, token);
            }
            return false;
        }
        // Event-queue scheduling, not a cosmetic delay: ownership transfer completes on return.
        if (!post(() -> {
                if (mSandiumHandoffToken == token && !mSandiumHandoffShuttingDown) requestRender();
            })) {
            clearSandiumNativeHandoff();
            CompositorViewJni.get().cancelSandiumNativeHandoff(mNativeCompositorView, token);
            return false;
        }
        return true;
    }

    private void clearSandiumNativeHandoff() {
        mSandiumHandoffToken = 0;
        mSandiumHandoffTab = null;
        mSandiumHandoffContents = null;
        mSandiumHandoffProvider = null;
        mSandiumHandoffHolderGate = null;
        mSandiumHandoffCompletion = null;
    }

    public void cancelSandiumNativeHandoff(long token) {
        org.chromium.base.ThreadUtils.assertOnUiThread();
        if (token == 0 || token != mSandiumHandoffToken) return;
        if (mSandiumHandoffStarting) {
            mSandiumHandoffBeginViolated = true;
            return; // Native begin has not yet transferred resource ownership.
        }
        org.chromium.base.@Nullable Callback<Boolean> completion = mSandiumHandoffCompletion;
        clearSandiumNativeHandoff();
        try {
            if (mNativeCompositorView != 0) {
                CompositorViewJni.get().cancelSandiumNativeHandoff(mNativeCompositorView, token);
            }
        } finally {
            if (completion != null) completion.onResult(false);
        }
        // Completion may tear down this view or install a different lease. No member writes here.
    }

    private boolean isSandiumNativeHandoffLocallyEligible(long token) {
        return !mSandiumHandoffShuttingDown && !mSandiumHandoffStarting
                && token > 0 && token == mSandiumHandoffToken && mNativeCompositorView != 0
                && !mIsDrawPaused && !mIsInXr && !mIsXrFullSpaceMode
                && !mOverlayVideoEnabled && !mSelectionHandlesActive
                && !mHasActiveTouchInterceptors && isAttachedToWindow()
                && hasWindowFocus() && getVisibility() == View.VISIBLE
                && mSandiumHandoffTab != null && !mSandiumHandoffTab.isDestroyed()
                && mSandiumHandoffContents != null && !mSandiumHandoffContents.isDestroyed()
                && mSandiumHandoffTab.getWebContents() == mSandiumHandoffContents;
    }

    @CalledByNative
    private @Nullable SceneLayer getSandiumNativeHandoffScene(long token) {
        org.chromium.base.ThreadUtils.assertOnUiThread();
        if (!isSandiumNativeHandoffLocallyEligible(token)) return null;
        org.chromium.chrome.browser.tab.@Nullable Tab tab = mSandiumHandoffTab;
        @Nullable WebContents contents = mSandiumHandoffContents;
        @Nullable LayoutProvider provider = mSandiumHandoffProvider;
        @Nullable SceneLayer scene = mSandiumFinalizedScene;
        java.util.function.@Nullable BooleanSupplier holderGate = mSandiumHandoffHolderGate;
        if (tab == null || contents == null || provider == null || scene == null
                || holderGate == null || provider != mSandiumFinalizationProvider
                || !holderGate.getAsBoolean() || !isSandiumNativeHandoffLocallyEligible(token)
                || provider != mSandiumFinalizationProvider
                || scene != mSandiumFinalizedScene) return null;
        // LayoutProvider is queried NOW; a layout can change after frame submission.
        @Nullable Layout layout = provider.getActiveLayout();
        if (layout == null || !layout.isSandiumNativeHandoffSceneEligible(tab, contents, scene)
                || !isSandiumNativeHandoffLocallyEligible(token) || provider != mSandiumFinalizationProvider
                || scene != mSandiumFinalizedScene) return null;
        return scene; // Native must ALSO reject a Java scene whose native pointer is now zero.
    }

    @CalledByNative
    private void onSandiumNativeHandoffComplete(long token, boolean presented) {
        org.chromium.base.ThreadUtils.assertOnUiThread();
        if (token == 0 || token != mSandiumHandoffToken) return;
        if (mSandiumHandoffStarting) {
            mSandiumHandoffBeginViolated = true;
            return; // Reject protocol violation without releasing an untransferred resource.
        }
        boolean stillEligible = presented && getSandiumNativeHandoffScene(token) != null;
        if (token != mSandiumHandoffToken) return; // Gate reentered and ended/replaced this lease.
        org.chromium.base.@Nullable Callback<Boolean> completion = mSandiumHandoffCompletion;
        clearSandiumNativeHandoff();
        if (completion != null) completion.onResult(stillEligible);
    }

    private void abandonSandiumNativeHandoffForShutdown() {
        org.chromium.base.ThreadUtils.assertOnUiThread();
        // Do not invoke arbitrary cleanup from teardown. Holder owns independent lease disposal.
        mSandiumHandoffShuttingDown = true;
        clearSandiumNativeHandoff();
        mSandiumFinalizationProvider = null;
        mSandiumFinalizedScene = null;
    }

'''
NATIVES='''        boolean beginSandiumNativeHandoff(
                long nativeCompositorView, long token, WebContents webContents);

        void cancelSandiumNativeHandoff(long nativeCompositorView, long token);

'''
def once(text, old, new):
    if text.count(old)!=1:raise ValueError('Pinned Java adapter anchor drift: '+old[:90])
    return text.replace(old,new,1)
def transform(text):
    if MARKER in text:
        if text.count(MARKER)!=1 or FIELDS not in text or METHODS not in text or NATIVES not in text:
            raise ValueError('Partial Java handoff adapter')
        return text
    text=once(text,'    private long mNativeCompositorView;\n',FIELDS+'    private long mNativeCompositorView;\n')
    text=once(text,'    /** Should be called for cleanup when the CompositorView instance is no longer used. */',METHODS+'    /** Should be called for cleanup when the CompositorView instance is no longer used. */')
    text=once(text,'    public void shutDown() {\n','    public void shutDown() {\n        abandonSandiumNativeHandoffForShutdown();\n')
    anchor='        CompositorViewJni.get().setSceneLayer(mNativeCompositorView, sceneLayer);'
    text=once(text,anchor,'        mSandiumFinalizationProvider = provider;\n        mSandiumFinalizedScene = sceneLayer;\n'+anchor)
    text=once(text,'        void finalizeLayers(long nativeCompositorView);',NATIVES+'        void finalizeLayers(long nativeCompositorView);')
    return text
def plan(root):
    path=Path(root)/PATH
    return {path:transform(path.read_text())}
