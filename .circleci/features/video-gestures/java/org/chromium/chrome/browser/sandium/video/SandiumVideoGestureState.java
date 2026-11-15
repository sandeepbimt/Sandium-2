// Copyright 2026 Sandium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license.
package org.chromium.chrome.browser.sandium.video;

/** Pure gesture policy. The native host owns eligibility, playback and window/audio state. */
public final class SandiumVideoGestureState {
    public enum Kind { NONE, TAP, SEEK, BRIGHTNESS, VOLUME }
    public static final class Result {
        public final Kind kind;
        // SEEK is relative milliseconds; brightness/volume are relative fractions of range.
        public final double delta;
        public final boolean commit;
        Result(Kind kind, double delta, boolean commit) {
            this.kind = kind;
            this.delta = delta;
            this.commit = commit;
        }
    }
    private static final Result NONE = new Result(Kind.NONE, 0, false);
    private final float mSlop;
    private final float mEdge;
    private boolean mTracking;
    private boolean mMoved;
    private float mX, mY, mWidth, mHeight;
    private long mDownTime;
    private Kind mKind = Kind.NONE;
    private double mDelta;

    public SandiumVideoGestureState(float slopPixels, float edgePixels) {
        if (!Float.isFinite(slopPixels) || slopPixels <= 0
                || !Float.isFinite(edgePixels) || edgePixels < 0) {
            throw new IllegalArgumentException("Invalid gesture thresholds");
        }
        mSlop = slopPixels;
        mEdge = edgePixels;
    }

    /** Called only after an explicit user opt-in to the native gesture surface. */
    public boolean down(float x, float y, float width, float height, long timeMillis) {
        cancel();
        if (!Float.isFinite(x) || !Float.isFinite(y) || !Float.isFinite(width)
                || !Float.isFinite(height) || width <= 2 * mEdge || height <= 2 * mEdge
                || x < mEdge || x > width - mEdge || y < mEdge || y > height - mEdge) {
            return false; // Leave edge/system gestures and invalid geometry alone.
        }
        mTracking = true;
        mX = x;
        mY = y;
        mWidth = width;
        mHeight = height;
        mDownTime = timeMillis;
        return true;
    }

    public Result move(float x, float y, int pointerCount, boolean seekable) {
        if (!mTracking) return NONE;
        if (pointerCount != 1 || !Float.isFinite(x) || !Float.isFinite(y)) {
            cancel();
            return NONE;
        }
        float dx = x - mX;
        float dy = y - mY;
        if (Math.max(Math.abs(dx), Math.abs(dy)) >= mSlop) mMoved = true;
        if (mKind == Kind.NONE && Math.max(Math.abs(dx), Math.abs(dy)) >= mSlop) {
            // Direction lock avoids volume changes from a predominantly horizontal seek.
            if (Math.abs(dx) > Math.abs(dy) * 1.2f) {
                if (!seekable) { cancel(); return NONE; }
                mKind = Kind.SEEK;
            } else if (Math.abs(dy) > Math.abs(dx) * 1.2f) {
                mKind = mX < mWidth / 2 ? Kind.BRIGHTNESS : Kind.VOLUME;
            } else {
                return NONE;
            }
        }
        if (mKind == Kind.SEEK && !seekable) { cancel(); return NONE; }
        if (mKind == Kind.SEEK) mDelta = clamp(dx / mWidth * 120_000.0, -120_000, 120_000);
        if (mKind == Kind.VOLUME || mKind == Kind.BRIGHTNESS) {
            mDelta = clamp(-dy / mHeight, -1, 1);
        }
        return new Result(mKind, mDelta, false);
    }

    public Result up(float x, float y, long timeMillis, boolean seekable) {
        if (!mTracking) return NONE;
        Result last = move(x, y, 1, seekable);
        if (!mTracking) return NONE;
        boolean centerTap = !mMoved && mKind == Kind.NONE && timeMillis >= mDownTime
                && timeMillis - mDownTime <= 350
                && Math.abs(x - mX) < mSlop && Math.abs(y - mY) < mSlop
                && mX >= mWidth / 3 && mX <= mWidth * 2 / 3;
        Result result = centerTap ? new Result(Kind.TAP, 0, true)
                : last.kind == Kind.NONE ? NONE : new Result(last.kind, last.delta, true);
        cancel();
        return result;
    }

    public void cancel() {
        mTracking = false;
        mMoved = false;
        mKind = Kind.NONE;
        mDelta = 0;
    }

    public static double clamp(double value, double low, double high) {
        return Math.max(low, Math.min(high, value));
    }
}
