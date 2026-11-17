#!/usr/bin/env python3
"""Move phone load progress paint into the capsule; native load/animation state stays authoritative."""
import argparse
from pathlib import Path
import subprocess
PIN='d331de35ca8ab1358c7a17e4bd41627d55eaef51'
BAR='chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/'
DRAW='chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/LocationBarBackgroundDrawable.java'
def once(s,old,new):
    if new in s:return s
    if s.count(old)!=1:raise ValueError('Address progress pinned anchor mismatch: '+old[:100])
    return s.replace(old,new,1)

def drawable(s):
    s=once(s,'    private final GradientDrawable mBackgroundGradient;', '''    // SANDIUM_ADDRESS_PROGRESS_V1: full-height translucent fill under URL/icons.
    private final Paint mSandiumProgressPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private float mSandiumProgress;
    private int mSandiumProgressAlpha;
    private boolean mSandiumProgressRtl;

    public void setSandiumProgress(float progress, int alpha, boolean rtl) {
        progress = Math.max(0f, Math.min(1f, progress));
        alpha = Math.max(0, Math.min(255, alpha));
        if (mSandiumProgress == progress && mSandiumProgressAlpha == alpha
                && mSandiumProgressRtl == rtl) return;
        mSandiumProgress = progress;
        mSandiumProgressAlpha = alpha;
        mSandiumProgressRtl = rtl;
        invalidateSelf();
    }

    private final GradientDrawable mBackgroundGradient;''')
    return once(s,'        mBackgroundGradient.draw(canvas);', '''        mBackgroundGradient.draw(canvas);
        if (mSandiumProgress > 0f && mSandiumProgressAlpha > 0 && !mEffectiveBounds.isEmpty()) {
            int saved = canvas.save();
            // Reuse the native rounded outline, insets and current focus geometry.
            canvas.clipPath(mOuterPath);
            float width = mEffectiveBounds.width() * mSandiumProgress;
            float left = mSandiumProgressRtl ? mEffectiveBounds.right - width : mEffectiveBounds.left;
            float right = mSandiumProgressRtl ? mEffectiveBounds.right : mEffectiveBounds.left + width;
            mSandiumProgressPaint.setColor(0xFF46C878);
            mSandiumProgressPaint.setAlpha(Math.round(0.22f * mSandiumProgressAlpha));
            canvas.drawRect(left, mEffectiveBounds.top, right, mEffectiveBounds.bottom,
                    mSandiumProgressPaint);
            canvas.restoreToCount(saved);
        }''')

def bar(s):
    s=once(s,'    /** Interface for progress bar animation interpolation logics. */', '''    // SANDIUM_ADDRESS_PROGRESS_V1: an optional paint owner, not another load state machine.
    private @Nullable Runnable mSandiumCapsuleListener;
    private boolean mSandiumProgressDetached;
    public boolean isSandiumProgressAttached() { return !mSandiumProgressDetached && isAttachedToWindow(); }

    public boolean isSandiumCapsuleProgressEnabled() { return mSandiumCapsuleListener != null; }

    public void setSandiumCapsuleProgressListener(@Nullable Runnable listener) {
        mSandiumCapsuleListener = listener;
        if (mAnimatingView != null) {
            mAnimatingView.setSandiumCapsuleProgressEnabled(listener != null);
        }
        invalidate();
        notifySandiumCapsuleProgress();
    }

    private void notifySandiumCapsuleProgress() {
        if (mSandiumCapsuleListener != null) mSandiumCapsuleListener.run();
    }

    @Override
    public void draw(android.graphics.Canvas canvas) {
        if (!isSandiumCapsuleProgressEnabled()) super.draw(canvas);
    }

    @Override
    protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        mSandiumProgressDetached = false;
        notifySandiumCapsuleProgress();
    }

    /** Interface for progress bar animation interpolation logics. */''')
    s=once(s,'        mAnimationLogic = new ProgressAnimationSmooth();', '''        mAnimationLogic = new ProgressAnimationSmooth();
        addObserver(new ProgressBarObserver() {
            @Override public void onVisibleProgressUpdated() { notifySandiumCapsuleProgress(); }
            @Override public void onCompositedLayersVisibilityChanged() { notifySandiumCapsuleProgress(); }
        });''')
    s=once(s,'        mAnimatingView = animatingView;', '''        mAnimatingView = animatingView;
        mAnimatingView.setSandiumCapsuleProgressEnabled(isSandiumCapsuleProgressEnabled());''')
    s=once(s,'        if (mAnimatingView != null) mAnimatingView.setAlpha(alpha);', '''        if (mAnimatingView != null) mAnimatingView.setAlpha(alpha);
        notifySandiumCapsuleProgress();''')
    s=once(s,'        super.onDetachedFromWindow();', '''        super.onDetachedFromWindow();
        mSandiumProgressDetached = true;
        notifySandiumCapsuleProgress();''')
    s=once(s, '                mAnimatingView.setVisibility(visibility);\n            }\n        }\n    }',
        '                mAnimatingView.setVisibility(visibility);\n            }\n        }\n        notifySandiumCapsuleProgress();\n    }')
    return s

def animating(s):
    return once(s,'    /** The drawable inside this ImageView. */', '''    // SANDIUM_ADDRESS_PROGRESS_V1: retain timing/state but not the old thin shimmer paint.
    private boolean mSandiumCapsuleProgressEnabled;
    public void setSandiumCapsuleProgressEnabled(boolean enabled) {
        mSandiumCapsuleProgressEnabled = enabled;
        invalidate();
    }
    @Override
    public void draw(android.graphics.Canvas canvas) {
        if (!mSandiumCapsuleProgressEnabled) super.draw(canvas);
    }

    /** The drawable inside this ImageView. */''')

def layer(s):
    return once(s,'        mControlContainer.getProgressBarDrawingInfo(drawingInfo);', '''        mControlContainer.getProgressBarDrawingInfo(drawingInfo);
        // SANDIUM_ADDRESS_PROGRESS_V1: progress is included in the phone toolbar bitmap.
        // Disable only its redundant thin compositor paint, not load state/observers.
        if (mProgressBarView.isSandiumCapsuleProgressEnabled()) {
            drawingInfo.visible = false;
            drawingInfo.progressBarColor = 0;
            drawingInfo.progressBarBackgroundColor = 0;
            drawingInfo.progressBarStaticBackgroundColor = 0;
            drawingInfo.progressBarRect.setEmpty();
            drawingInfo.progressBarBackgroundRect.setEmpty();
            drawingInfo.progressBarStaticBackgroundRect.setEmpty();
            return;
        }''')

def phone(s):
    s=once(s,'    private LocationBarBackgroundDrawable mLocationBarBackground;', '''    private final org.chromium.components.browser_ui.widget.ClipDrawableProgressBar.DrawingInfo
            mSandiumProgressInfo = new org.chromium.components.browser_ui.widget.ClipDrawableProgressBar.DrawingInfo();

    private int sandiumProgressAlpha() {
        ToolbarProgressBar progress = getProgressBar();
        if (!progress.isSandiumProgressAttached() || isInTabSwitcherMode()) return 0;
        progress.getDrawingInfo(mSandiumProgressInfo);
        return android.graphics.Color.alpha(mSandiumProgressInfo.progressBarColor);
    }

    private void updateSandiumAddressProgress() {
        if (mLocationBarBackground == null) return;
        mLocationBarBackground.setSandiumProgress(getProgressBar().getProgress(),
                sandiumProgressAlpha(), getLayoutDirection() == View.LAYOUT_DIRECTION_RTL);
        // Invalidate the native toolbar/capture through its existing scheduling path.
        invalidate();
    }

    private LocationBarBackgroundDrawable mLocationBarBackground;''')
    # The coordinator exists only after native toolbar initialize has installed progressBar.
    s=once(s,'        mLocationBarBackground = createModernLocationBarBackground(getContext());', '''        mLocationBarBackground = createModernLocationBarBackground(getContext());
        getProgressBar().setSandiumCapsuleProgressListener(this::updateSandiumAddressProgress);''')
    s=once(s,'    public void destroy() {', '''    public void destroy() {
        getProgressBar().setSandiumCapsuleProgressListener(null);''')
    # This is after capture-coherence; retain the original overload and forward-icon state.
    s=once(s,'                mHomeButton.getImageAlpha());', '''                mHomeButton.getImageAlpha()).withSandiumProgressAlpha(sandiumProgressAlpha());''')
    return s

def token(s):
    s=once(s,'    private final int mUrlBarWidth;', '''    private final int mUrlBarWidth;
    private float mSandiumProgress;
    private int mSandiumProgressAlpha;

    PhoneCaptureStateToken withSandiumProgressAlpha(int alpha) {
        mSandiumProgressAlpha = alpha;
        if (alpha == 0) mSandiumProgress = 0;
        return this;
    }''')
    s=once(s,'''        // Progress is not currently used for comparing snapshot states. It isn't part of the bitmap
        // capture anyway.''', '''        // SANDIUM_ADDRESS_PROGRESS_V1: capsule fill is now part of the toolbar bitmap.
        mSandiumProgress = progress;''')
    s=once(s,'        } else if (current.mTint != next.mTint) {', '''        } else if (current.mSandiumProgress != next.mSandiumProgress
                || current.mSandiumProgressAlpha != next.mSandiumProgressAlpha) {
            return ToolbarSnapshotDifference.UNKNOWN;
        } else if (current.mTint != next.mTint) {''')
    return s

TRANSFORMS={DRAW:drawable,BAR+'ToolbarProgressBar.java':bar,
    BAR+'ToolbarProgressBarAnimatingView.java':animating,BAR+'ToolbarProgressBarLayer.java':layer,
    BAR+'top/ToolbarPhone.java':phone,BAR+'top/PhoneCaptureStateToken.java':token}

def apply(src,verify=False):
    if subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()!=PIN:
        raise ValueError('Unexpected Chromium pin')
    result={src/p:fn((src/p).read_text()) for p,fn in TRANSFORMS.items()}
    if verify:
        if any(p.read_text()!=out for p,out in result.items()):raise ValueError('Missing capsule progress overlay')
    else:
        for p,out in result.items():p.write_text(out)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('src',type=Path);p.add_argument('--verify-only',action='store_true');a=p.parse_args();apply(a.src,a.verify_only)
