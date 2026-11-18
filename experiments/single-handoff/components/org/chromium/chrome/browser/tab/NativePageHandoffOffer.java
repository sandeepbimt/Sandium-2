package org.chromium.chrome.browser.tab;

import android.view.View;
import java.util.function.BooleanSupplier;
import org.chromium.build.annotations.Nullable;
import org.chromium.chrome.browser.ui.native_page.NativePage;
import org.chromium.content_public.browser.WebContents;

/** Single-use offer of an ALREADY retired native page, scoped to one synchronous notification. */
public final class NativePageHandoffOffer {
    /** Claimed resource owner; close clears retained references before external destruction. */
    public static final class Claim implements AutoCloseable {
        private @Nullable Tab mTab;
        private @Nullable NativePage mPage;
        private @Nullable View mView;
        private @Nullable WebContents mContents;
        private @Nullable BooleanSupplier mValid;
        private @Nullable Runnable mDispose;
        private final Thread mThread = Thread.currentThread();
        private Claim(Tab tab, NativePage page, View view, WebContents contents,
                BooleanSupplier valid, Runnable dispose) {
            mTab = tab; mPage = page; mView = view; mContents = contents;
            mValid = valid; mDispose = dispose;
        }
        private void checkThread() {
            if (Thread.currentThread() != mThread) throw new IllegalStateException();
        }
        public boolean isValid() {
            checkThread();
            BooleanSupplier valid = mValid;
            return valid != null && valid.getAsBoolean() && mValid == valid;
        }
        public Tab tab() { checkThread(); if (mTab == null) throw new IllegalStateException(); return mTab; }
        public NativePage page() { checkThread(); if (mPage == null) throw new IllegalStateException(); return mPage; }
        public View view() { checkThread(); if (mView == null) throw new IllegalStateException(); return mView; }
        public WebContents contents() { checkThread(); if (mContents == null) throw new IllegalStateException(); return mContents; }
        @Override public void close() {
            checkThread();
            Runnable dispose = mDispose;
            mTab = null; mPage = null; mView = null; mContents = null;
            mValid = null; mDispose = null;
            if (dispose != null) dispose.run();
        }
    }
    private @Nullable Claim mAvailable;
    private boolean mClaiming;
    private final Thread mThread = Thread.currentThread();
    NativePageHandoffOffer(Tab tab, NativePage page, View view, WebContents contents,
            BooleanSupplier valid, Runnable dispose) {
        mAvailable = new Claim(tab, page, view, contents, valid, dispose);
    }
    private void checkThread() {
        if (Thread.currentThread() != mThread) throw new IllegalStateException();
    }
    /** No ownership moves on null. A successful claim owns cleanup even if later JNI begin fails. */
    public @Nullable Claim claim(Tab tab, View outgoingView) {
        checkThread();
        Claim candidate = mAvailable;
        if (candidate == null || mClaiming || candidate.tab() != tab
                || candidate.view() != outgoingView) return null;
        mClaiming = true;
        try {
            if (!candidate.isValid() || mAvailable != candidate) return null;
            mAvailable = null;
            return candidate;
        } finally { mClaiming = false; }
    }
    /** Called in TabImpl finally. A claimed resource is no longer this offer's responsibility. */
    void closeUnclaimed() {
        checkThread();
        Claim candidate = mAvailable;
        mAvailable = null;
        if (candidate != null) candidate.close();
    }
}
