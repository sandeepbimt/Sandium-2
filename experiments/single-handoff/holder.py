"""Dormant native-home ownership transfer and holder integration; explicit experimental profile."""
from pathlib import Path
TAB='chrome/android/java/src/org/chromium/chrome/browser/tab/TabImpl.java'
OBSERVER='chrome/browser/tab/java/src/org/chromium/chrome/browser/tab/TabObserver.java'
NTP='chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPage.java'
HOLDER='chrome/android/java/src/org/chromium/chrome/browser/compositor/CompositorViewHolder.java'
ACTIVITY='chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java'
MARKER='SANDIUM_NATIVE_HOME_OFFER_V1'
OFFER_BLOCK='''        // SANDIUM_NATIVE_HOME_OFFER_V1
        // Only the explicit committed showRenderedPage route may offer a retired regular NTP.
        if (notify && postHideTask == null && expectedHandoffRevision != null
                && expectedHandoffRevision == mSandiumNativeHandoffRevision
                && expectedHandoffContents != null && expectedHandoffContents == mWebContents
                && !expectedHandoffContents.isDestroyed() && !isDestroyed() && !isIncognito()
                && ("http".equals(getUrl().getScheme()) || "https".equals(getUrl().getScheme()))
                && previousNativePage instanceof NativePageHandoffSource
                && !previousNativePage.isFrozen() && previousNativePage.getView() != null
                && !mSandiumNativeHandoffReservations.containsKey(previousNativePage)) {
            final NativePage page = previousNativePage;
            final View retiredView = page.getView();
            assumeNonNull(retiredView);
            final Object revision = expectedHandoffRevision;
            final WebContents contents = expectedHandoffContents;
            final Object reservation = new Object();
            mSandiumNativeHandoffReservations.put(page, reservation);
            NativePageHandoffOffer offer = new NativePageHandoffOffer(
                    this, page, retiredView, contents,
                    () -> !isDestroyed() && revision == mSandiumNativeHandoffRevision
                            && mWebContents == contents && !contents.isDestroyed()
                            && mNativePage == null,
                    () -> {
                        // No overlapping offer can own this resource while cleanup mutates its View.
                        if (mSandiumNativeHandoffReservations.get(page) != reservation) return;
                        mSandiumNativeHandoffReservations.remove(page);
                        if (page != mNativePage) destroyNativePageInternal(page);
                    });
            try {
                for (TabObserver observer : mObservers) {
                    observer.onNativePageHandoffOffered(this, offer);
                }
                notifyContentChanged();
            } finally {
                // Nested notify may consume/close this exact offer, never a mutable current offer.
                offer.closeUnclaimed();
            }
            return;
        }
'''
OBSERVER_HOOK='''    /** Single-use retired native-home offer, valid only during the following content notification. */
    default void onNativePageHandoffOffered(Tab tab, NativePageHandoffOffer offer) {}

'''
def once(s,a,b):
    if s.count(a)!=1:raise ValueError('Native holder anchor drift: '+a[:90])
    return s.replace(a,b,1)
def transform(path,s):
    if path==OBSERVER:
        if OBSERVER_HOOK in s:return s
        if 'onNativePageHandoffOffered' in s:raise ValueError('Partial offer observer')
        return once(s,'    default void onContentChanged(Tab tab) {}',OBSERVER_HOOK+'    default void onContentChanged(Tab tab) {}')
    if path==NTP:
        anchor='        implements NativePage,'
        new='        implements org.chromium.chrome.browser.tab.NativePageHandoffSource, NativePage,'
        if new in s:return s
        return once(s,anchor,new)
    if path!=TAB:raise ValueError('Holder source not implemented: '+path)
    if MARKER in s:
        if (s.count(MARKER)!=1 or OFFER_BLOCK not in s
                or s.count('private final java.util.IdentityHashMap<NativePage, Object> mSandiumNativeHandoffReservations = new java.util.IdentityHashMap<>();')!=1
                or s.count('if (mSandiumNativeHandoffReservations.containsKey(nativePage)) return;')!=1
                or s.count('hideNativePage(true, null, mSandiumNativeHandoffRevision, mWebContents);')!=1):
            raise ValueError('Partial native offer')
        return s
    s=once(s,'class TabImpl implements Tab, TabInternal {','class TabImpl implements Tab, TabInternal {\n    private Object mSandiumNativeHandoffRevision = new Object();\n    private final java.util.IdentityHashMap<NativePage, Object> mSandiumNativeHandoffReservations = new java.util.IdentityHashMap<>();')
    s=once(s,'        if (mNativePage != null) hideNativePage(true, null);',
        '        if (mNativePage != null) {\n            hideNativePage(true, null, mSandiumNativeHandoffRevision, mWebContents);\n        }')
    anchor='    private void hideNativePage(boolean notify, @Nullable Runnable postHideTask) {'
    s=once(s,anchor,'''    private void hideNativePage(boolean notify, @Nullable Runnable postHideTask) {
        hideNativePage(notify, postHideTask, null, null);
    }

    private void hideNativePage(boolean notify, @Nullable Runnable postHideTask,
            @Nullable Object expectedHandoffRevision, @Nullable WebContents expectedHandoffContents) {''')
    anchor='        if (postHideTask != null) postHideTask.run();\n        if (notify) notifyContentChanged();'
    s=once(s,anchor,'        if (postHideTask != null) postHideTask.run();\n'+OFFER_BLOCK+'        if (notify) notifyContentChanged();')
    s=once(s,'    private void destroyNativePageInternal(@Nullable NativePage nativePage) {\n        if (nativePage == null) return;',
        '    private void destroyNativePageInternal(@Nullable NativePage nativePage) {\n        if (nativePage == null) return;\n        // The outstanding offer owns disposal, including nested restore-then-retire.\n        if (mSandiumNativeHandoffReservations.containsKey(nativePage)) return;')
    s=once(s,'        transitionType &= PageTransition.CORE_MASK;','        mSandiumNativeHandoffRevision = new Object();\n        transitionType &= PageTransition.CORE_MASK;')
    s=once(s,'    void showNativePage(NativePage nativePage) {','    void showNativePage(NativePage nativePage) {\n        mSandiumNativeHandoffRevision = new Object();')
    if s.count('mWebContents = webContents;')!=2:raise ValueError('WC binding inventory')
    s=s.replace('mWebContents = webContents;','mSandiumNativeHandoffRevision = new Object();\n        mWebContents = webContents;')
    s=once(s,'        mWebContents = null;','        mSandiumNativeHandoffRevision = new Object();\n        mWebContents = null;')
    return s
def plan(root):
    root=Path(root)
    return {root/p:transform(p,(root/p).read_text()) for p in (TAB,OBSERVER,NTP)}
