"""Extend the exact bundled wallpaper into the settled Home toolbar's live paint band."""
import argparse
from pathlib import Path

from glue import once
import seal

BASE = '20d75958f7187f1d248327cebe7be10fb46fc265'
MAN = '11a70465ba5d5dce08ac115efc76f29b24f57c2864d1276e0818e823f82b6c7c'
PROOF = '0f6860b12738e359ef3262342e2d42b864d0876ab480413a57673576ab664e0f'
FEED = ('chrome/android/feed/core/java/src/org/chromium/chrome/browser/feed/'
        'FeedSurfaceCoordinator.java')
HOME = 'chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPage.java'
MANAGER = 'chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java'
PHONE = ('chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/'
         'ToolbarPhone.java')
OWNERS = {
    FEED: 'f4faf529926a4f6a14188c1fafa679e13d3aba7264f3824c8afb7fdb2bb2fcfb',
    HOME: '17bbab93f80a9bd680c917d8246ca98ad9c02ad83e41799ab7a2a38ba073c254',
    MANAGER: 'f46a5940acf19055d146f14caa0d950656c2c85160d8f1232082518a2658aa9c',
    PHONE: '6f9c1bbec280bdeb9423682aafa84b009d41c16482fba4f8ab91a14148512a3f',
}


def transform(path, raw):
    t = raw.decode()
    if path == FEED:
        for place, imported in (('BitmapFactory', 'BitmapShader'), ('Color', 'Matrix'),
                                 ('RectF', 'Shader')):
            anchor = f'import android.graphics.{place};'
            t = once(t, anchor, anchor + f'\nimport android.graphics.{imported};')
        anchor = '    private final Paint mRawSHomeWallpaperPaint = new Paint(Paint.FILTER_BITMAP_FLAG);'
        t = once(t, anchor, anchor + '''
    private final Paint mRawSHomeToolbarWallpaperPaint = new Paint(Paint.FILTER_BITMAP_FLAG);
    private final Matrix mRawSHomeToolbarWallpaperMatrix = new Matrix();
    private final int[] mRawSHomeToolbarLocation = new int[2];
    private @Nullable BitmapShader mRawSHomeToolbarWallpaperShader;
    private boolean mRawSHomeToolbarGeometryDirty;''')
        anchor = '                        owner.mRawSHomeWallpaperBitmap = bitmap;'
        t = once(t, anchor, anchor + '''
                        owner.mRawSHomeToolbarWallpaperShader = bitmap == null ? null
                                : new BitmapShader(bitmap, Shader.TileMode.CLAMP,
                                        Shader.TileMode.CLAMP);''')
        t = once(t, '            disconnectRawSHomeWallpaper();\n            cancelRawSHomeImageUpload();',
                 '            disconnectRawSHomeWallpaper();\n'
                 '            if (mRawSHomeWallpaperPainting) invalidateRawSHomeCompanionPaint();\n'
                 '            cancelRawSHomeImageUpload();')
        t = once(t, '        mRawSHomeWallpaperBitmap = null;',
                 '        mRawSHomeWallpaperBitmap = null;\n'
                 '        mRawSHomeToolbarWallpaperShader = null;\n'
                 '        mRawSHomeToolbarWallpaperPaint.setShader(null);')
        t = once(t, """        if (mRawSHomePublishedWallpaperPainting != mRawSHomeWallpaperPainting) {
            mRawSHomePublishedWallpaperPainting = mRawSHomeWallpaperPainting;
            Runnable invalidate = mRawSHomeStatusBarInvalidator;
            if (invalidate != null) invalidate.run();
        }
        return true;
    }
""", """        if (mRawSHomeToolbarGeometryDirty
                || mRawSHomePublishedWallpaperPainting != mRawSHomeWallpaperPainting) {
            mRawSHomeToolbarGeometryDirty = false;
            mRawSHomePublishedWallpaperPainting = mRawSHomeWallpaperPainting;
            invalidateRawSHomeCompanionPaint();
        }
        return true;
    }

    private void invalidateRawSHomeCompanionPaint() {
        Runnable invalidate = mRawSHomeStatusBarInvalidator;
        if (invalidate != null) invalidate.run();
    }
""")
        t = once(t, '            mRawSHomeWallpaperDest.set(mRawSHomeWallpaperCandidate);',
                 '            mRawSHomeWallpaperDest.set(mRawSHomeWallpaperCandidate);\n'
                 '            mRawSHomeToolbarGeometryDirty = true;')
        anchor = '    private void drawRawSHomeWallpaper(Canvas canvas) {'
        t = once(t, anchor, '''    /**
     * Draw the active artwork in the toolbar's own already-reserved live paint bounds.
     * Reuse the Home transform in window coordinates; clamp at its last image row instead
     * of changing the page crop or stretching a second copy. No layout or snapshot changes.
     */
    public boolean drawRawSHomeToolbarWallpaper(Canvas canvas, View toolbar) {
        Bitmap bitmap = mRawSHomeWallpaperBitmap;
        BitmapShader shader = mRawSHomeToolbarWallpaperShader;
        RectF dest = mRawSHomeWallpaperDest;
        if (!mRawSHomeWallpaperPainting || mRawSHomeWallpaperIncludesBrand
                || mRawSHomeNativeImageActive || bitmap == null || shader == null
                || !mRootView.isAttachedToWindow() || !mRootView.isShown()
                || !mRootView.isLaidOut() || mRootView.isLayoutRequested()
                || !mRootView.getMatrix().isIdentity() || !toolbar.getMatrix().isIdentity()
                || mRootView.getWindowToken() != toolbar.getWindowToken()
                || mRawSHomeWallpaperWidth != mRootView.getWidth()
                || mRawSHomeWallpaperHeight != mRootView.getHeight()
                || dest.isEmpty() || toolbar.getWidth() <= 0 || toolbar.getHeight() <= 0) {
            return false;
        }
        mRootView.getLocationInWindow(mRawSHomeRootLocation);
        toolbar.getLocationInWindow(mRawSHomeToolbarLocation);
        int x = mRawSHomeToolbarLocation[0] - mRawSHomeRootLocation[0];
        int y = mRawSHomeToolbarLocation[1] - mRawSHomeRootLocation[1];
        if (x < -1 || x + toolbar.getWidth() > mRootView.getWidth() + 1
                || y < mRootView.getHeight() - toolbar.getHeight()
                || y > mRootView.getHeight() + 2) {
            return false;
        }
        mRawSHomeToolbarWallpaperMatrix.setScale(
                dest.width() / bitmap.getWidth(), dest.height() / bitmap.getHeight());
        mRawSHomeToolbarWallpaperMatrix.postTranslate(dest.left - x, dest.top - y);
        shader.setLocalMatrix(mRawSHomeToolbarWallpaperMatrix);
        mRawSHomeToolbarWallpaperPaint.setShader(shader);
        canvas.drawRect(0, 0, toolbar.getWidth(), toolbar.getHeight(),
                mRawSHomeToolbarWallpaperPaint);
        return true;
    }

''' + anchor)
    elif path == HOME:
        anchor = '            if (toolbar != null) toolbar.getStatusBarColorController().updateStatusBarColor();'
        t = once(t, anchor, '''            if (toolbar != null) {
                toolbar.getStatusBarColorController().updateStatusBarColor();
                toolbar.invalidateRawSHomeToolbarBacking();
            }''')
        anchor = '    /** Provides the paint color of the active regular Home to the existing status bar owner. */'
        t = once(t, anchor, '''    /** Paint-only request from the bottom toolbar of this exact active tab. */
    public boolean drawRawSHomeToolbarWallpaper(Canvas canvas, View toolbar) {
        return !mIsDestroyed && !mTab.isHidden() && !mTab.isOffTheRecord()
                && mTab.getNativePage() == this && mActivityTabProvider.get() == mTab
                && mTab.getView() == getView()
                && mBrowserControlsStateProvider.getContentOffset() == 0
                && mBrowserControlsStateProvider.getBottomControlOffset() == 0
                && mFeedSurfaceProvider instanceof FeedSurfaceCoordinator coordinator
                && coordinator.drawRawSHomeToolbarWallpaper(canvas, toolbar);
    }

''' + anchor)
    elif path == MANAGER:
        anchor = '        mToolbarLayout = mActivity.findViewById(R.id.toolbar);'
        t = once(t, anchor, anchor + '''
        if (mToolbarLayout instanceof ToolbarPhone phone) {
            phone.setRawSHomeToolbarBackingPainter((canvas, toolbar) -> {
                NewTabPage home = getNewTabPageForCurrentTab();
                return home != null && home.drawRawSHomeToolbarWallpaper(canvas, toolbar);
            });
        }''')
        anchor = '    private @Nullable NewTabPage getNewTabPageForCurrentTab() {'
        t = once(t, anchor, '''    public void invalidateRawSHomeToolbarBacking() {
        if (mToolbarLayout instanceof ToolbarPhone) mToolbarLayout.invalidate();
    }

''' + anchor)
    elif path == PHONE:
        # No dependency on the Chrome/Feed Java targets from the toolbar module.
        anchor = '    private final ColorDrawable mRawSSoftBacking = new ColorDrawable();'
        t = once(t, anchor, anchor + '''
    private final GradientDrawable mRawSHomeToolbarScrim = new GradientDrawable(
            GradientDrawable.Orientation.TOP_BOTTOM, new int[] {0x00000000, 0x16000000});
    private java.util.function.@Nullable BiPredicate<Canvas, View> mRawSHomeToolbarBackingPainter;''')
        anchor = '    @Override\n    protected void dispatchDraw(Canvas canvas) {\n        int rawSBackingColor'
        t = once(t, anchor, '''    public void setRawSHomeToolbarBackingPainter(
            java.util.function.BiPredicate<Canvas, View> painter) {
        mRawSHomeToolbarBackingPainter = painter;
    }

    @Override
    protected void dispatchDraw(Canvas canvas) {
        int rawSBackingColor''')
        t = once(t, '''        if (rawSBackingColor != Color.TRANSPARENT) {
            mRawSSoftBacking.setColor(rawSBackingColor);''', '''        var painter = mRawSHomeToolbarBackingPainter;
        if (rawSBackingColor != Color.TRANSPARENT && isRawSBottomNativeHomeOmnibox()
                && Color.alpha(mCurrentLocationBarColor) == 255
                && painter != null && painter.test(canvas, this)) {
            // The wallpaper owns the backing now. Do not draw either opaque toolbar layer.
            mRawSHomeToolbarScrim.setBounds(0, 0, getWidth(), getHeight());
            mRawSHomeToolbarScrim.draw(canvas);
        } else if (rawSBackingColor != Color.TRANSPARENT) {
            mRawSSoftBacking.setColor(rawSBackingColor);''')
    else:
        raise ValueError(path)
    return t.encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if Path.cwd() != Path(__file__).resolve().parents[1]:
        raise ValueError('run in checkout root')
    read = lambda name: seal.git('show', BASE + ':' + name)
    out = seal.plan(read, owners=OWNERS, edit=transform, man=MAN, proof=PROOF)
    if args.write:
        if seal.git('rev-parse', 'HEAD').decode().strip() != BASE:
            raise ValueError('wrong checkout')
        for name, data in out.items():
            p = Path(name)
            if p.is_symlink() or (p.exists() and p.read_bytes() !=
                    (data if name.startswith(seal.IMAGE) else read(name))):
                raise ValueError('dirty or unsafe overlay path: ' + name)
    for name, data in sorted(out.items()):
        if args.write:
            Path(name).write_bytes(data)
        print(seal.digest(data), name)


if __name__ == '__main__':
    main()
