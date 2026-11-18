"""Dormant native-home wallpaper preparation ownership; no visibility delay/cache."""
from pathlib import Path
PATH='brave/android/java/org/chromium/chrome/browser/ntp/BraveNewTabPageLayout.java'
MARKER='SANDIUM_WALLPAPER_REQUEST_OWNER_V1'
FIELDS='''    // SANDIUM_WALLPAPER_REQUEST_OWNER_V1
    private Object mSandiumWallpaperLifecycle = new Object();
    private boolean mSandiumWallpaperReleased;
    private boolean mSandiumWallpaperSuspended;
    private @Nullable Object mSandiumWallpaperProfile;
    private @Nullable NTPImage mSandiumRequestedWallpaper;
    private @Nullable ImageView mSandiumWallpaperTarget;
    private @Nullable Object mSandiumWallpaperRequest;
    private int mSandiumWallpaperWidth;
    private int mSandiumWallpaperHeight;
    private ViewTreeObserver.@Nullable OnGlobalLayoutListener mSandiumWallpaperLayoutObserver;

'''
METHODS='''    private boolean isSandiumWallpaperSelectionAllowed() {
        return !mSandiumWallpaperReleased && !mSandiumWallpaperSuspended
                && mSandiumWallpaperCoordinator != null && mProfile != null
                && UserPrefs.get(mProfile).getBoolean(BravePref.NEW_TAB_PAGE_SHOW_BACKGROUND_IMAGE)
                && mSponsoredTab != null && NTPImageUtil.shouldEnableNTPFeature()
                && mNtpImageGlobal != null
                && !(mNtpImageGlobal instanceof Wallpaper
                        && ((Wallpaper) mNtpImageGlobal).isRichMedia());
    }

    private Object cancelSandiumWallpaperRequest() {
        final Object revision = new Object();
        mSandiumWallpaperLifecycle = revision;
        // Invalidate before cancellation or observer removal can reenter.
        mSandiumWallpaperRequest = null;
        mSandiumRequestedWallpaper = null;
        mSandiumWallpaperProfile = null;
        mSandiumWallpaperWidth = 0;
        mSandiumWallpaperHeight = 0;
        @Nullable ImageView target = mSandiumWallpaperTarget;
        ViewTreeObserver.@Nullable OnGlobalLayoutListener listener = mSandiumWallpaperLayoutObserver;
        mSandiumWallpaperTarget = null;
        mSandiumWallpaperLayoutObserver = null;
        @Nullable FetchWallpaperWorkerTask task = mWorkerTask;
        mWorkerTask = null;
        if (task != null) task.cancel(true);
        if (target != null && listener != null) {
            ViewTreeObserver observer = target.getViewTreeObserver();
            if (observer.isAlive()) observer.removeOnGlobalLayoutListener(listener);
        }
        return revision;
    }

    private boolean isSandiumWallpaperSelectionCurrent(Object revision, NTPImage image, ImageView target) {
        return mSandiumWallpaperLifecycle == revision && mSandiumRequestedWallpaper == image
                && mSandiumWallpaperProfile != null && mSandiumWallpaperProfile == mProfile
                && mSandiumWallpaperTarget == target && mBgImageView == target
                && mNtpImageGlobal == image && isSandiumWallpaperSelectionAllowed();
    }

    private boolean isSandiumWallpaperRequestCurrent(Object request, NTPImage image,
            ImageView target, @Nullable Object profile, int width, int height) {
        return profile != null && mProfile == profile && mSandiumWallpaperProfile == profile
                && mSandiumWallpaperRequest == request && mSandiumRequestedWallpaper == image
                && mNtpImageGlobal == image && mSandiumWallpaperTarget == target
                && mBgImageView == target && isSandiumWallpaperSelectionAllowed()
                && target.getMeasuredWidth() == width && target.getMeasuredHeight() == height
                && mActivity != null && !mActivity.isFinishing() && !mActivity.isDestroyed();
    }

    private void prepareSandiumWallpaper() {
        @Nullable NTPImage image = mSandiumRequestedWallpaper;
        @Nullable ImageView target = mSandiumWallpaperTarget;
        if (image == null || target == null || !isSandiumWallpaperSelectionAllowed()
                || mSandiumWallpaperProfile == null || mSandiumWallpaperProfile != mProfile
                || image != mNtpImageGlobal || target != mBgImageView) return;
        int width = target.getMeasuredWidth();
        int height = target.getMeasuredHeight();
        if (width <= 0 || height <= 0) return;
        if (mSandiumWallpaperRequest != null && width == mSandiumWallpaperWidth
                && height == mSandiumWallpaperHeight) return;
        final @Nullable Object profile = mProfile;
        final Object request = new Object();
        mSandiumWallpaperRequest = request;
        mSandiumWallpaperWidth = width;
        mSandiumWallpaperHeight = height;
        @Nullable FetchWallpaperWorkerTask previous = mWorkerTask;
        mWorkerTask = null;
        if (previous != null) previous.cancel(true);
        if (!isSandiumWallpaperRequestCurrent(request, image, target, profile, width, height)) return;
        FetchWallpaperWorkerTask task = new FetchWallpaperWorkerTask(image, width, height,
                new FetchWallpaperWorkerTask.WallpaperRetrievedCallback() {
                    @Override
                    public void bgWallpaperRetrieved(Bitmap bitmap) {
                        if (!isSandiumWallpaperRequestCurrent(request, image, target, profile, width, height)
                                || bitmap == null || bitmap.isRecycled()
                                || bitmap.getWidth() != width || bitmap.getHeight() != height) return;
                        // Existing callback owns bitmap assignment and backing readiness notification.
                        // Never recycle a stale result here: the worker retains bitmap ownership.
                        mWallpaperRetrievedCallback.bgWallpaperRetrieved(bitmap);
                    }
                    @Override
                    public void logoRetrieved(Wallpaper wallpaper, Bitmap bitmap) {
                        if (!isSandiumWallpaperRequestCurrent(request, image, target, profile, width, height)) return;
                        mWallpaperRetrievedCallback.logoRetrieved(wallpaper, bitmap);
                    }
                });
        mWorkerTask = task;
        task.executeOnExecutor(AsyncTask.THREAD_POOL_EXECUTOR);
    }

    private void selectSandiumWallpaper(NTPImage image) {
        @Nullable ImageView target = mBgImageView;
        if (target == null || !isSandiumWallpaperSelectionAllowed() || image != mNtpImageGlobal) {
            cancelSandiumWallpaperRequest();
            return;
        }
        if (mSandiumRequestedWallpaper != image || mSandiumWallpaperTarget != target
                || mSandiumWallpaperProfile != mProfile) {
            final Object revision = cancelSandiumWallpaperRequest();
            if (mSandiumWallpaperLifecycle != revision || target != mBgImageView
                    || image != mNtpImageGlobal || !isSandiumWallpaperSelectionAllowed()) return;
            mSandiumRequestedWallpaper = image;
            mSandiumWallpaperTarget = target;
            mSandiumWallpaperProfile = mProfile;
            target.setScaleType(ImageView.ScaleType.MATRIX);
            if (!isSandiumWallpaperSelectionCurrent(revision, image, target)) return;
            // Never present the previous selection as if it were the newly selected wallpaper.
            // Clearing the drawable releases only this View reference, not worker-owned pixels.
            target.setImageDrawable(null);
            if (!isSandiumWallpaperSelectionCurrent(revision, image, target)) return;
            if (mSandiumWallpaperCoordinator != null) {
                mSandiumWallpaperCoordinator.onSandiumWallpaperBitmapChanged();
            }
            if (!isSandiumWallpaperSelectionCurrent(revision, image, target)) return;
            final ViewTreeObserver.OnGlobalLayoutListener listener = () -> prepareSandiumWallpaper();
            mSandiumWallpaperLayoutObserver = listener;
            target.getViewTreeObserver().addOnGlobalLayoutListener(listener);
            if (!isSandiumWallpaperSelectionCurrent(revision, image, target)) {
                ViewTreeObserver observer = target.getViewTreeObserver();
                if (observer.isAlive()) observer.removeOnGlobalLayoutListener(listener);
                return;
            }
        }
        // Prepare now when final dimensions already exist. Otherwise normal layout will retry.
        // No attachment hold, pre-draw veto, arbitrary timer, or outgoing website overlay.
        prepareSandiumWallpaper();
    }

'''
def once(s,a,b):
 if s.count(a)!=1:raise ValueError('Wallpaper request anchor drift: '+a[:100])
 return s.replace(a,b,1)
def transform(s):
 if MARKER in s:
  required=('selectSandiumWallpaper(ntpImage);',
   '    public void releaseSandiumWallpaperBacking() {\n        mSandiumWallpaperReleased = true;\n        cancelSandiumWallpaperRequest();',
   '    protected void onDetachedFromWindow() {\n        mSandiumWallpaperSuspended = true;\n        if (mSandiumWallpaperCoordinator != null) cancelSandiumWallpaperRequest();',
   '    protected void onAttachedToWindow() {\n        mSandiumWallpaperSuspended = false;',
   '    private void maybeShowNTPImage() {\n        if (mSandiumWallpaperCoordinator != null && !isSandiumWallpaperSelectionAllowed()) {\n            cancelSandiumWallpaperRequest();\n        }')
  if FIELDS not in s or METHODS not in s or any(s.count(x)!=1 for x in required):
   raise ValueError('Partial wallpaper request owner')
  return s
 if 'mSandiumWallpaperCoordinator' not in s:raise ValueError('Requires existing native wallpaper backing')
 s=once(s,'    private @Nullable FetchWallpaperWorkerTask mWorkerTask;',FIELDS+'    private @Nullable FetchWallpaperWorkerTask mWorkerTask;')
 s=once(s,'    private void setBackgroundImage(NTPImage ntpImage) {',METHODS+'''    private void setBackgroundImage(NTPImage ntpImage) {
        if (mSandiumWallpaperCoordinator != null) {
            selectSandiumWallpaper(ntpImage);
            return;
        }''')
 s=once(s,'    public void releaseSandiumWallpaperBacking() {','    public void releaseSandiumWallpaperBacking() {\n        mSandiumWallpaperReleased = true;\n        cancelSandiumWallpaperRequest();')
 s=once(s,'    protected void onDetachedFromWindow() {','    protected void onDetachedFromWindow() {\n        mSandiumWallpaperSuspended = true;\n        if (mSandiumWallpaperCoordinator != null) cancelSandiumWallpaperRequest();')
 s=once(s,'    protected void onAttachedToWindow() {','    protected void onAttachedToWindow() {\n        mSandiumWallpaperSuspended = false;')
 s=once(s,'    private void maybeShowNTPImage() {','''    private void maybeShowNTPImage() {
        if (mSandiumWallpaperCoordinator != null && !isSandiumWallpaperSelectionAllowed()) {
            cancelSandiumWallpaperRequest();
        }''')
 return s
def plan(root):
 p=Path(root)/PATH
 return {p:transform(p.read_text())}
