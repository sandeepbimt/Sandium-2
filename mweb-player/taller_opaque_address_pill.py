"""Apply the frozen taller-pill design without changing the native toolbar's measured height."""
from glue import once
from home_toolbar_wallpaper import FEED, HOME, MANAGER, PHONE

BASE = '50d224e8986653b69b839d10d0a29b9215d6c896'
OWNERS = {
    FEED: '84b8e1f9ad0056d66867464d212e45b12c32a5c401c599ab9b819cb370adf0f6',
    HOME: '63604a0bc856d6e8f879521fd4fbe1b2c9f7b98e01bc27b7a43aa6a0d26502a3',
    MANAGER: '94b640ebebd1cd191023870e497b2880e6bc22f12c7d0acf561c1f667b2e22b2',
    PHONE: 'a3c5ad47639ba66f01fedd61f971c0b46452d0178b51aebd06c84ab57a1ee2c0',
}


def transform(path, raw):
    s = raw.decode()

    def edit(old, new=''):
        nonlocal s
        s = once(s, old, new)

    def remove(start, end):
        i = s.index(start)
        j = s.index(end, i + len(start))
        edit(s[i:j])

    if path == PHONE:
        edit('''    private final GradientDrawable mRawSHomeToolbarScrim = new GradientDrawable(
            GradientDrawable.Orientation.TOP_BOTTOM, new int[] {0x00000000, 0x16000000});
    private java.util.function.@Nullable BiPredicate<Canvas, View> mRawSHomeToolbarBackingPainter;
''')
        remove('    public void setRawSHomeToolbarBackingPainter(',
               '    @Override\n    protected void dispatchDraw(Canvas canvas)')
        old = '''        var painter = mRawSHomeToolbarBackingPainter;
        if (rawSBackingColor != Color.TRANSPARENT && isRawSBottomNativeHomeOmnibox()
                && Color.alpha(mCurrentLocationBarColor) == 255
                && painter != null && painter.test(canvas, this)) {
            // The wallpaper owns the backing now. Do not draw either opaque toolbar layer.
            mRawSHomeToolbarScrim.setBounds(0, 0, getWidth(), getHeight());
            mRawSHomeToolbarScrim.draw(canvas);
        } else if (rawSBackingColor != Color.TRANSPARENT) {'''
        edit(old, '''        // Home and web use the same opaque band; only the native compositor
        // paints that band when it owns the separately captured toolbar.
        if (rawSBackingColor != Color.TRANSPARENT) {''')
        edit('''? getRawSUnifiedCapsuleVerticalExtra(inset, rest)''',
             '''? getRawSUnifiedCapsuleVerticalExtra(rest)''')
        edit('''    /** Extends only the paint, not the actual layout or Chromium's focus expansion. */
    private int getRawSUnifiedCapsuleVerticalExtra(int inset, float rest) {
        int verticalInset = mLocationBarBackgroundVerticalInset - calculateOnFocusHeightIncrease();
        return Math.min(Math.max(0, verticalInset), Math.round(inset * rest));
    }''', '''    /** Extends only the paint, leaving a slim opaque strip at rest on either edge. */
    private int getRawSUnifiedCapsuleVerticalExtra(float rest) {
        int verticalInset = mLocationBarBackgroundVerticalInset - calculateOnFocusHeightIncrease();
        int extraSpace = Math.max(0, verticalInset - rawSDp(2));
        int desiredExtra = Math.round(rawSDp(6) * Math.min(1f, Math.max(0f, rest)));
        return Math.min(extraSpace, desiredExtra);
    }''')
    elif path == MANAGER:
        edit('''        if (mToolbarLayout instanceof ToolbarPhone phone) {
            phone.setRawSHomeToolbarBackingPainter((canvas, toolbar) -> {
                NewTabPage home = getNewTabPageForCurrentTab();
                return home != null && home.drawRawSHomeToolbarWallpaper(canvas, toolbar);
            });
        }
''')
        remove('    public void invalidateRawSHomeToolbarBacking() {',
               '    private @Nullable NewTabPage getNewTabPageForCurrentTab() {')
    elif path == HOME:
        edit('                toolbar.invalidateRawSHomeToolbarBacking();\n')
        remove('    /** Paint-only request from the bottom toolbar of this exact active tab. */',
               '    /** Provides the paint color of the active regular Home to the existing status bar owner. */')
    elif path == FEED:
        for imported in ('BitmapShader', 'Matrix', 'Shader'):
            edit(f'import android.graphics.{imported};\n')
        remove('    private final Paint mRawSHomeToolbarWallpaperPaint',
               '    private final Rect mRawSHomeWallpaperVisible')
        edit('''                        owner.mRawSHomeToolbarWallpaperShader = bitmap == null ? null
                                : new BitmapShader(bitmap, Shader.TileMode.CLAMP,
                                        Shader.TileMode.CLAMP);
''')
        edit('''        mRawSHomeToolbarWallpaperShader = null;
        mRawSHomeToolbarWallpaperPaint.setShader(null);
''')
        edit('''        if (mRawSHomeToolbarGeometryDirty
                || mRawSHomePublishedWallpaperPainting != mRawSHomeWallpaperPainting) {
            mRawSHomeToolbarGeometryDirty = false;''',
             '''        if (mRawSHomePublishedWallpaperPainting != mRawSHomeWallpaperPainting) {''')
        edit('            mRawSHomeToolbarGeometryDirty = true;\n')
        remove('    /**\n     * Draw the active artwork in the toolbar\'s own already-reserved live paint bounds.',
               '    private void drawRawSHomeWallpaper(Canvas canvas) {')
    else:
        raise ValueError(path)
    return s.encode()
