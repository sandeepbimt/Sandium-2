    // SANDIUM_NATIVE_REVEAL_V1: optional inverse dependency, no recorder module import.
    public interface SandiumRevealObserver {
        long epoch(Tab tab);
        void record(Tab tab, long epoch, boolean controls, double[] values);
    }
    private static volatile @Nullable SandiumRevealObserver sSandiumRevealObserver;
    private static long sSandiumRevealSequence;
    private @Nullable SandiumRevealProbe mSandiumRevealProbe;
    public static void setSandiumRevealObserver(@Nullable SandiumRevealObserver observer) {
        sSandiumRevealObserver = observer;
    }
    private boolean sandiumRevealEnabled() {
        try {
            return sSandiumRevealObserver != null && sSandiumRevealObserver.epoch(mTab) != 0;
        } catch (RuntimeException ignored) { return false; }
    }
    private void stopSandiumReveal(int stage) {
        if (mSandiumRevealProbe != null) mSandiumRevealProbe.finish(stage);
        mSandiumRevealProbe = null;
    }
    private void beginSandiumReveal() {
        stopSandiumReveal(4);
        SandiumRevealObserver sink = sSandiumRevealObserver;
        if (sink == null || android.os.Looper.myLooper() != android.os.Looper.getMainLooper()) return;
        try {
            long epoch = sink.epoch(mTab);
            if (epoch == 0) return;
            View outer = getView();
            View foreground = outer;
            if (mFeedSurfaceProvider instanceof FeedSurfaceCoordinator
                    && ((FeedSurfaceCoordinator) mFeedSurfaceProvider).hasSandiumWallpaperRoot()) {
                foreground = ((FeedSurfaceCoordinator) mFeedSurfaceProvider).getSandiumForegroundView();
            }
            mSandiumRevealProbe = new SandiumRevealProbe(sink, epoch, outer, foreground);
            mSandiumRevealProbe.arm();
        } catch (RuntimeException ignored) { stopSandiumReveal(4); }
    }
    private final class SandiumRevealProbe implements android.view.ViewTreeObserver.OnPreDrawListener,
            View.OnAttachStateChangeListener {
        private final SandiumRevealObserver mSink;
        private final long mEpoch;
        private final long mSample = ++sSandiumRevealSequence;
        private final long mDeadlineMs = android.os.SystemClock.uptimeMillis() + 500;
        private final View mOuter;
        private final View mForeground;
        private final android.os.Handler mHandler = new android.os.Handler(android.os.Looper.getMainLooper());
        private final Runnable mTimeout = () -> finish(5);
        private final android.view.ViewTreeObserver mTree;
        private int mFrames;
        private boolean mFinished;
        private boolean mAfterReveal;
        SandiumRevealProbe(SandiumRevealObserver sink, long epoch, View outer, View foreground) {
            mSink = sink; mEpoch = epoch; mOuter = outer; mForeground = foreground;
            mTree = outer.getViewTreeObserver();
        }
        void arm() {
            mOuter.addOnAttachStateChangeListener(this);
            mTree.addOnPreDrawListener(this);
            mHandler.postDelayed(mTimeout, 500);
            sample(0);
        }
        private void view(int stage, int kind, View view) {
            int[] location = new int[2];
            boolean attached = view.isAttachedToWindow();
            if (attached) view.getLocationInWindow(location);
            var params = view.getLayoutParams();
            int top = params instanceof ViewGroup.MarginLayoutParams
                    ? ((ViewGroup.MarginLayoutParams) params).topMargin : 0;
            int bottom = params instanceof ViewGroup.MarginLayoutParams
                    ? ((ViewGroup.MarginLayoutParams) params).bottomMargin : 0;
            mSink.record(mTab, mEpoch, false, new double[] {mSample, stage, mFrames, kind,
                    attached ? 1 : 0, location[0], location[1], view.getWidth(), view.getHeight(),
                    top, bottom, view.getTranslationX(), view.getTranslationY(), view.getAlpha(),
                    view.getScrollX(), view.getScrollY()});
        }
        void sample(int stage) {
            if (mFinished) return;
            if (stage != 5 && android.os.SystemClock.uptimeMillis() >= mDeadlineMs) { finish(5); return; }
            try {
                if (mSink != sSandiumRevealObserver || mSink.epoch(mTab) != mEpoch) { finish(-1); return; }
                view(stage, 0, mOuter);
                view(stage, 1, mForeground);
                mSink.record(mTab, mEpoch, true, new double[] {mSample, stage, mFrames,
                        mBrowserControlsStateProvider.getContentOffset(),
                        mBrowserControlsStateProvider.getTopControlsHeight(),
                        mBrowserControlsStateProvider.getTopControlOffset(),
                        mBrowserControlsStateProvider.getBottomControlsHeight(),
                        mBrowserControlsStateProvider.getBottomControlOffset(),
                        mBrowserControlsStateProvider.getControlsPosition(),
                        mTab.getView() == mOuter ? 1 : 0});
            } catch (RuntimeException ignored) { finish(-1); }
        }
        void afterReveal() {
            sample(8);
            mAfterReveal = true;
        }
        void finish(int stage) {
            if (mFinished) return;
            // Mark done before removing listeners; never emit recursively on a failing sink.
            if (stage >= 0) sample(stage);
            mFinished = true;
            mHandler.removeCallbacks(mTimeout);
            mOuter.removeOnAttachStateChangeListener(this);
            if (mTree.isAlive()) mTree.removeOnPreDrawListener(this);
            var current = mOuter.getViewTreeObserver();
            if (current != mTree && current.isAlive()) current.removeOnPreDrawListener(this);
        }
        @Override public boolean onPreDraw() {
            if (!mFinished) {
                if (android.os.SystemClock.uptimeMillis() >= mDeadlineMs) { finish(5); return true; }
                // Reserve one sampled draw for after the native completion callback.
                if (!mAfterReveal && mFrames >= 15) return true;
                ++mFrames;
                sample(2);
                if (mAfterReveal) finish(9);
            }
            return true;
        }
        @Override public void onViewAttachedToWindow(View view) {}
        @Override public void onViewDetachedFromWindow(View view) { finish(6); }
    }
