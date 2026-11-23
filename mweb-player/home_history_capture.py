"""RawS #1516: align a history thumbnail with the settled bottom Home view."""

import hashlib

NTP = 'chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPage.java'
BASE_PAGE = ('chrome/browser/ui/android/native_page/java/src/org/chromium/chrome/'
             'browser/ui/native_page/NativePage.java')
CAPTURER = ('chrome/browser/gesturenav/android/java/src/org/chromium/chrome/'
            'browser/gesturenav/NativePageBitmapCapturer.java')
OWNERS = {NTP: '15b9dd5a2297dc2a0e3eba0273fb65f78ad9fbc0dda8eba24baeaee3a0a1578b'}
TRACKED = {
    BASE_PAGE: '52a7d5b84ef91be9a2f60c8f75ebbfe396eabaf6cfa3962944d15bbdcb7c6d38',
    CAPTURER: 'b2dcf0b188c6892953f964fb83126048386c1eab843ca0fd71fa4cecbadb8474',
}
GIT_BLOBS = {
    BASE_PAGE: '3014d2084ef691eddc02e74e3047e220725a229b',
    CAPTURER: '4a8420ac29e9d9378c5d6f8b67b3d0ea21cba0c3',
}


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('unexpected Home history capture anchor: ' + old)
    return text.replace(old, new, 1)


BASE_CONTRACT = '''    /**
     * Returns the vertical overlap to remove when recording a history screenshot in
     * view-local coordinates. Synchronous fullscreen captures still use the ordinary overlap.
     */
    default int getHeightOverlappedForHistoryScreenshot() {
        return getHeightOverlappedWithTopControls();
    }

'''

HOME_CONTRACT = '''    @Override
    public int getHeightOverlappedForHistoryScreenshot() {
        int overlap = getHeightOverlappedWithTopControls();
        if (overlap != 0 || !"io.github.sandeepbimt.raws".equals(mContext.getPackageName())
                || mIsLff || mIsDestroyed || mTab.isDestroyed() || mTab.isHidden()
                || mTab.isOffTheRecord() || mActivityTabProvider.get() != mTab
                || mTab.getNativePage() != this
                || mBrowserControlsStateProvider.getControlsPosition() != ControlsPosition.BOTTOM
                || mBrowserControlsStateProvider.getContentOffset() != 0
                || mBrowserControlsStateProvider.getBottomControlOffset() != 0
                || mTabStripHeightSupplier.get() != 0 || mToolbarHeight <= 0) {
            return overlap;
        }

        View root = getView();
        if (mTab.getView() != root || !root.isAttachedToWindow() || !root.isLaidOut()
                || root.isLayoutRequested() || !root.getMatrix().isIdentity()
                || !(root.getLayoutParams() instanceof ViewGroup.MarginLayoutParams margins)
                || root.getTop() != margins.topMargin || root.getTop() != -mToolbarHeight
                || root.getHeight() <= mToolbarHeight) {
            return overlap;
        }

        // The live attached root starts one toolbar height above the viewport origin
        // (see updateMargins). View.draw records at local y=0, and the history layer
        // is placed at viewport y=0. Remove the actual clipped top overlap once.
        return -root.getTop();
    }

'''


def transform(path, data):
    if (OWNERS | TRACKED).get(path) != hashlib.sha256(data).hexdigest():
        raise ValueError('unexpected pinned Home history capture preimage: ' + path)
    text = data.decode()
    if path == NTP:
        anchor = '    @Override\n    public void reload() {'
        result = once(text, anchor, HOME_CONTRACT + anchor)
    elif path == BASE_PAGE:
        anchor = '    /**\n     * @return {@code true} if the native page is in inactive/frozen state.\n'
        result = once(text, anchor, BASE_CONTRACT + anchor)
    else:
        result = once(text,
                      '                                    0, -tab.getNativePage().getHeightOverlappedWithTopControls());',
                      '                                    0, -tab.getNativePage().getHeightOverlappedForHistoryScreenshot());')
        result = once(result,
                      '''            bitmap.eraseColor(assumeNonNull(tab.getNativePage()).getBackgroundColor());''',
                      '''            NativePage page = assumeNonNull(tab.getNativePage());
            bitmap.eraseColor(page.getBackgroundColor());''')
        result = once(result,
                      '''            canvas.translate(
                    0,
                    -tab.getNativePage().getHeightOverlappedWithTopControls()
                            + (fullscreen ? topControlsHeight : 0));''',
                      '''            int overlap = fullscreen
                    ? page.getHeightOverlappedWithTopControls()
                    : page.getHeightOverlappedForHistoryScreenshot();
            canvas.translate(0, -overlap + (fullscreen ? topControlsHeight : 0));''')
    return result.encode()
