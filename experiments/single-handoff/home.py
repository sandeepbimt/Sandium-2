"""Single-owner native-home admission. Pure plan; requires exact pinned delegates."""
from pathlib import Path
DELEGATE='chrome/android/java/src/org/chromium/chrome/browser/ntp/NtpSmoothTransitionDelegate.java'
TAB='chrome/android/java/src/org/chromium/chrome/browser/tab/TabImpl.java'
HERE=Path(__file__).parent
FIELDS='''    // SANDIUM_HOME_HANDOFF_V1: one operation owns readiness, animator and completion.
    private int mGeneration;
    private @Nullable Runnable mOnEnd;
    private @Nullable android.view.ViewTreeObserver mPendingTree;
    private @Nullable android.view.ViewTreeObserver.OnPreDrawListener mPendingDraw;
    private boolean mFeedReady;
    private final View.OnAttachStateChangeListener mAttachListener =
            new View.OnAttachStateChangeListener() {
                @Override public void onViewAttachedToWindow(View view) { awaitLayout(mGeneration); }
                @Override public void onViewDetachedFromWindow(View view) { complete(mGeneration); }
            };

    private @Nullable Callback<Integer> mOnScrollStateChanged;
    private @Nullable Runnable mFallback;
    private long mDeadlineMs;

    private void clearReadiness() {
        if (mOnScrollStateChanged != null) mRestoringState.removeObserver(mOnScrollStateChanged);
        mOnScrollStateChanged = null;
        if (mFallback != null) mHandler.removeCallbacks(mFallback);
        mFallback = null;
        mView.removeOnAttachStateChangeListener(mAttachListener);
        if (mPendingTree != null && mPendingTree.isAlive() && mPendingDraw != null) {
            mPendingTree.removeOnPreDrawListener(mPendingDraw);
        }
        mPendingTree = null;
        mPendingDraw = null;
    }

    private void complete(int generation) {
        if (generation != mGeneration || mOnEnd == null) return;
        Runnable end = mOnEnd;
        mOnEnd = null;
        ++mGeneration;
        clearReadiness();
        mAnimator.removeAllListeners();
        mAnimator.cancel();
        mView.setAlpha(1f);
        end.run();
    }

    private void awaitLayout(int generation) {
        if (generation != mGeneration || mOnEnd == null || !mFeedReady
                || mAnimatorStarted || mPendingDraw != null || !mView.isAttachedToWindow()) return;
        mPendingTree = mView.getViewTreeObserver();
        mPendingDraw = () -> {
            if (generation != mGeneration || mOnEnd == null) return true;
            if (android.os.SystemClock.uptimeMillis() >= mDeadlineMs) {
                complete(generation);
                return true;
            }
            // Observe a real traversal; do not move controls or synthesize margins.
            if (!mView.isAttachedToWindow() || !mView.isLaidOut()
                    || mView.isLayoutRequested() || mView.getWidth() <= 0 || mView.getHeight() <= 0) return true;
            if (mPendingTree != null && mPendingTree.isAlive()) mPendingTree.removeOnPreDrawListener(mPendingDraw);
            mPendingTree = null;
            mPendingDraw = null;
            mAnimatorStarted = true;
            BackPressMetrics.recordNTPSmoothTransitionMethod(false);
            mAnimator.start();
            return true;
        };
        mPendingTree.addOnPreDrawListener(mPendingDraw);
    }
'''
METHODS='''    @Override
    public void prepare() {
        final int before = mGeneration;
        cancel();
        if (mGeneration != before + 1) return; // Completion installed a newer operation.
        mView.setAlpha(0f);
    }

    @Override
    public void start(Runnable onEnd) {
        // Settle the old operation BEFORE installing the new callback.
        final int before = mGeneration;
        cancel();
        if (mGeneration != before + 1) {
            // Reentrant completion installed a newer owner. Settle this superseded request.
            onEnd.run();
            return;
        }
        final int generation = ++mGeneration;
        mOnEnd = onEnd;
        mAnimatorStarted = false;
        mFeedReady = false;
        mAnimator = buildSmoothTransition(mView);
        mView.setAlpha(0f);
        mAnimator.addListener(new AnimatorListenerAdapter() {
            @Override public void onAnimationEnd(Animator animation) { complete(generation); }
        });
        mView.addOnAttachStateChangeListener(mAttachListener);
        // Existing native fallback budget bounds feed+layout+animation as one operation.
        mDeadlineMs = android.os.SystemClock.uptimeMillis()
                + BackPressMetrics.MAX_FALLBACK_DELAY_NTP_SMOOTH_TRANSITION;
        mFallback = () -> {
            if (generation != mGeneration || mOnEnd == null) return;
            BackPressMetrics.recordNTPSmoothTransitionMethod(true);
            complete(generation);
        };
        mHandler.postDelayed(mFallback, BackPressMetrics.MAX_FALLBACK_DELAY_NTP_SMOOTH_TRANSITION);
        mOnScrollStateChanged = restoreState -> {
            if (generation != mGeneration || mOnEnd == null) return;
            if (restoreState == FeedSurfaceProvider.RestoringState.NO_STATE_TO_RESTORE
                    || restoreState == FeedSurfaceProvider.RestoringState.RESTORED) {
                mFeedReady = true;
                if (mOnScrollStateChanged != null) mRestoringState.removeObserver(mOnScrollStateChanged);
                awaitLayout(generation);
            }
        };
        mRestoringState.addSyncObserverAndPostIfNonNull(mOnScrollStateChanged);
    }

    @Override
    public void cancel() {
        if (mOnEnd != null) { complete(mGeneration); return; }
        ++mGeneration;
        clearReadiness();
        mAnimator.removeAllListeners();
        mAnimator.cancel();
        mAnimatorStarted = false;
        mView.setAlpha(1f);
    }

'''
def once(s,a,b):
 if s.count(a)!=1:raise ValueError('Native home anchor drift: '+a[:80])
 return s.replace(a,b,1)
def delegate(s):
 original=(HERE/'fixtures/NtpSmoothTransitionDelegate.java').read_text()
 a=original[original.index('    final Callback<Integer> mOnScrollStateChanged ='):original.index('    public NtpSmoothTransitionDelegate(')]
 s=once(s,a,FIELDS+'\n')
 a=original[original.index('    @Override\n    public void prepare()'):original.index('    private static Animator buildSmoothTransition')]
 return once(s,a,METHODS)
TAB_HELPER = """    // SANDIUM_HOME_HANDOFF_V3: one terminal acknowledgement per WAIT owner.
    private long mSandiumHandoffGeneration;
    private long mSandiumWaitGeneration = -1;
    private long mSandiumEndedGeneration = -1;
    private boolean mSandiumHandoffPending;
    private @Nullable NativePage mSandiumHandoffPage;
    private @Nullable View mSandiumHandoffView;
    private @Nullable WebContents mSandiumHandoffContents;
    private boolean isSandiumHandoffCurrent(long generation, @Nullable NativePage page,
            @Nullable View view, @Nullable WebContents contents, int stage) {
        return !isDestroyed() && generation == mSandiumHandoffGeneration
                && page != null && mNativePage == page && getView() == view
                && contents != null && getWebContents() == contents && !contents.isDestroyed()
                && contents.getCurrentBackForwardTransitionStage() == stage;
    }
    private boolean settleSandiumHandoff(long generation, @Nullable NativePage page,
            @Nullable View view, @Nullable WebContents contents) {
        if (!mSandiumHandoffPending || contents == null
                || !isSandiumHandoffCurrent(generation, page, view, contents,
                        AnimationStage.WAITING_FOR_EMBEDDER_CONTENT_FOR_COMMITTED_ENTRY)) return false;
        // Retire before native callbacks, which can synchronously select another transition.
        mSandiumHandoffPending = false;
        mSandiumHandoffPage = null;
        mSandiumHandoffView = null;
        mSandiumHandoffContents = null;
        contents.onContentForNavigationEntryShown();
        return true;
    }
    private boolean retireSandiumHandoff() {
        final long generation = mSandiumHandoffGeneration;
        final boolean retiringWait = mSandiumWaitGeneration == generation;
        final @Nullable NativePage page = mNativePage;
        final @Nullable View view = getView();
        final @Nullable WebContents contents = getWebContents();
        // Same-owner detach/cancel releases native waiting; this is not presentation proof.
        settleSandiumHandoff(generation, mSandiumHandoffPage,
                mSandiumHandoffView, mSandiumHandoffContents);
        if (generation != mSandiumHandoffGeneration) {
            // Native completion normally emits NONE synchronously. Continue old cleanup only
            // for that same terminal owner, never after a newer transition or page replacement.
            return !isDestroyed() && mSandiumEndedGeneration == generation
                    && page == mNativePage && view == getView() && contents != null
                    && contents == getWebContents() && !contents.isDestroyed()
                    && contents.getCurrentBackForwardTransitionStage() == AnimationStage.NONE;
        }
        invalidateSandiumHandoff();
        // Duplicate WAIT notifications after detach must not re-arm the retired owner.
        if (retiringWait) mSandiumWaitGeneration = mSandiumHandoffGeneration;
        return true;
    }
    private void invalidateSandiumHandoff() {
        mSandiumHandoffPending = false;
        mSandiumHandoffPage = null;
        mSandiumHandoffView = null;
        mSandiumHandoffContents = null;
        ++mSandiumHandoffGeneration;
    }
"""
def tab(s):
 s=once(s,'    private @Nullable SmoothTransitionDelegate mNativePageSmoothTransitionDelegate;',
        '    private @Nullable SmoothTransitionDelegate mNativePageSmoothTransitionDelegate;\n'+TAB_HELPER)
 s=once(s,'    private void hideNativePage(boolean notify, @Nullable Runnable postHideTask) {',
        '    private void hideNativePage(boolean notify, @Nullable Runnable postHideTask) {\n        if (!retireSandiumHandoff()) return;')
 # Every explicit native delegate cancellation invalidates queued UI callbacks first.
 old='mNativePageSmoothTransitionDelegate.cancel();'
 if s.count(old)!=4:raise ValueError('Native cancellation inventory drift')
 import re
 s=re.sub(r'(?m)^( +)mNativePageSmoothTransitionDelegate.cancel\(\);\n +mNativePageSmoothTransitionDelegate = null;',
          lambda x:x[1]+'final SmoothTransitionDelegate retiringDelegate = mNativePageSmoothTransitionDelegate;\n'
              +x[1]+'mNativePageSmoothTransitionDelegate = null;\n'
              +x[1]+'final boolean stillOwner = retireSandiumHandoff();\n'
              +x[1]+'if (!stillOwner) return;\n'
              +x[1]+'retiringDelegate.cancel();',s)
 s=once(s,'                                && nativePage.getView() == view) {',
        '                                && nativePage.getView() == view) {\n                            if (!retireSandiumHandoff()) return;')
 # Rebinding even the same WC must not revive an old presentation callback.
 old='mWebContents = webContents;'
 if s.count(old)!=2:raise ValueError('WebContents binding inventory drift')
 s=re.sub(r'(?m)^( +)mWebContents = webContents;',
          lambda x:x[1]+'invalidateSandiumHandoff();\n'+x[0],s)
 s=once(s,'        mWebContents = null;', '        invalidateSandiumHandoff();\n        mWebContents = null;')
 a="""        switch (webContents.getCurrentBackForwardTransitionStage()) {
            case AnimationStage.NONE:"""
 b="""        final int handoffStage = webContents.getCurrentBackForwardTransitionStage();
        // OTHER starts/restarts presentation; NONE retires even without a delegate.
        if (handoffStage == AnimationStage.NONE) mSandiumEndedGeneration = mSandiumHandoffGeneration;
        if (handoffStage == AnimationStage.NONE || handoffStage == AnimationStage.OTHER) {
            invalidateSandiumHandoff();
        }
        final long handoffGeneration = mSandiumHandoffGeneration;
        final @Nullable NativePage handoffPage = mNativePage;
        switch (handoffStage) {
            case AnimationStage.NONE:"""
 s=once(s,a,b)
 a="""                                var currView = getView();
                                if (currView != null) {
                                    currView.setAlpha(0f);
                                }"""
 b="""                                if (!isSandiumHandoffCurrent(handoffGeneration, handoffPage,
                                        view, webContents, AnimationStage.OTHER)) return;
                                view.setAlpha(0f);"""
 s=once(s,a,b)
 a="""                                if (isDestroyed()) return;
                                WebContents currentWebContents = getWebContents();
                                if (currentWebContents == null
                                        || currentWebContents.isDestroyed()) {
                                    return;
                                }
                                currentWebContents.onContentForNavigationEntryShown();"""
 b="""                                if (!isSandiumHandoffCurrent(handoffGeneration, handoffPage,
                                        view, webContents,
                                        AnimationStage.WAITING_FOR_EMBEDDER_CONTENT_FOR_COMMITTED_ENTRY)) return;
                                if (!settleSandiumHandoff(handoffGeneration, handoffPage, view, webContents)) return;
                                final boolean normalTerminal = mSandiumEndedGeneration == handoffGeneration
                                        && webContents.getCurrentBackForwardTransitionStage() == AnimationStage.NONE;
                                if (isDestroyed() || webContents.isDestroyed() || (handoffGeneration != mSandiumHandoffGeneration && !normalTerminal)
                                        || mNativePage != handoffPage || getView() != view
                                        || getWebContents() != webContents) return;"""
 s=once(s,a,b)
 a='                                    if (isDestroyed() || webContents.isDestroyed()) return;'
 b="""                                    if (!isSandiumHandoffCurrent(handoffGeneration, handoffPage,
                                            view, webContents,
                                            AnimationStage.WAITING_FOR_EMBEDDER_CONTENT_FOR_COMMITTED_ENTRY)) return;"""
 s=once(s,a,b)
 s=once(s,"""                                    webContents.onContentForNavigationEntryShown();""",
          """                                    if (!settleSandiumHandoff(handoffGeneration, handoffPage, view, webContents)) return;""")
 s=once(s,"""            case AnimationStage.WAITING_FOR_EMBEDDER_CONTENT_FOR_COMMITTED_ENTRY:
                if (mNativePageSmoothTransitionDelegate != null) {""","""            case AnimationStage.WAITING_FOR_EMBEDDER_CONTENT_FOR_COMMITTED_ENTRY:
                if (mSandiumWaitGeneration == handoffGeneration) return;
                mSandiumWaitGeneration = handoffGeneration;
                mSandiumHandoffPending = handoffPage != null;
                mSandiumHandoffPage = handoffPage;
                mSandiumHandoffView = view;
                mSandiumHandoffContents = webContents;
                if (mNativePageSmoothTransitionDelegate != null) {""")
 # Native cancel must acknowledge even if queued OTHER never hid this view.
 s=once(s,"""                    if (view.getAlpha() != 1f) {
                        // This means the content/ is waiting for the NTP to be fully visible.""","""                    {
                        // Current native cancellation needs one ack even when already opaque.""")
 # Install no shared delegate after calling start: completion can be synchronous/reentrant.
 s=once(s,"""                    mNativePageSmoothTransitionDelegate.start(""","""                    final SmoothTransitionDelegate handoffDelegate = mNativePageSmoothTransitionDelegate;
                    mNativePageSmoothTransitionDelegate = null;
                    handoffDelegate.start(""")
 s=once(s,"""                            });
                    mNativePageSmoothTransitionDelegate = null;
                } else if (isNativePage()) { // Navigation from native page was cancelled.""","""                            });
                } else if (isNativePage()) { // Navigation from native page was cancelled.""")
 return s

def plan(root):
 root=Path(root)
 return {root/DELEGATE:delegate((root/DELEGATE).read_text()),root/TAB:tab((root/TAB).read_text())}
