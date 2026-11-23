"""Exact RawS resting bottom-toolbar paint, including the compositor handoff."""

import hashlib

JAVA = 'chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/'
CC = 'chrome/browser/android/compositor/'
PHONE = JAVA + 'ToolbarPhone.java'
TOOLBAR = JAVA + 'Toolbar.java'
COORD = JAVA + 'TopToolbarCoordinator.java'
CONTAINER = JAVA + 'ToolbarControlContainer.java'
FACTORY_J = JAVA + 'ResourceFactory.java'
FACTORY_C = CC + 'resources/resource_factory.cc'
RESOURCE_C = CC + 'resources/toolbar_resource.cc'
RESOURCE_H = CC + 'resources/toolbar_resource.h'
LAYER_C = CC + 'layer/toolbar_layer.cc'
LAYER_H = CC + 'layer/toolbar_layer.h'

OWNERS = {'chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/ToolbarPhone.java': 'edd7360934e6f5986f682d1e4a86d47fbecd5b2d70a3ca00a35d890737c94a31',
 'chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/Toolbar.java': '1c605e4debd209fb43308f0cdc2ec72730d159bd742e84a9246864762d441eff',
 'chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/TopToolbarCoordinator.java': '94217f96c9a7845518c6bb7be49d89ec64e4d6157bac918774ec971314406a86',
 'chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/ToolbarControlContainer.java': '8dd315c90f7401201d7a40c44e7ae1d9370f3967a635f528bba282b98bec1ddb',
 'chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/ResourceFactory.java': '9115db100cf2c72f11d35db8a50c5786715647bdce1081a8e26364b4b0cd86e8',
 'chrome/browser/android/compositor/resources/resource_factory.cc': '9d8b2c618f9c057a16e97134a9c6b306b119e992e620abac0a75ab1f5189c206',
 'chrome/browser/android/compositor/resources/toolbar_resource.cc': 'eba3440d02888bc1440611856509132c6f9e7d9fb10dd03e7983c85c185ed4eb',
 'chrome/browser/android/compositor/resources/toolbar_resource.h': 'ea87fd2b1a4ccab4bb90b0465d4dcf3f1ca1764ed5a57d3378f9df41a5f158c5',
 'chrome/browser/android/compositor/layer/toolbar_layer.cc': '8202315d5014e9d850b351feca77a6430a7d9668cfaa950402d704e478f68471',
 'chrome/browser/android/compositor/layer/toolbar_layer.h': '81011a23067bcfefe133005a25e028b029587cfedf3b1099516510fbaec43f93'}

def digest(data):
    return hashlib.sha256(data).hexdigest()


def transform(path: str, data: bytes) -> bytes:
    if OWNERS.get(path) != digest(data):
        raise ValueError(f'Unexpected soft shadow preimage: {path}')
    text = data.decode('utf-8')

    def edit(old, new):
        nonlocal text
        if text.count(old) != 1:
            raise ValueError(f'Ambiguous shadow anchor in {path}: {old[:90]!r}')
        text = text.replace(old, new, 1)

    if path == PHONE:
        edit('import org.chromium.ui.accessibility.KeyboardFocusUtil;',
             'import org.chromium.content_public.browser.NavigationHandle;\n'
             'import org.chromium.content_public.browser.WebContents;\n'
             'import org.chromium.ui.accessibility.KeyboardFocusUtil;')
        edit('import org.chromium.ui.util.KeyboardNavigationListener;',
             'import org.chromium.ui.util.KeyboardNavigationListener;\n'
             'import org.chromium.url.GURL;')
        edit('    protected ColorDrawable mToolbarBackground;',
             '''    protected ColorDrawable mToolbarBackground;
    private final ColorDrawable mRawSSoftBacking = new ColorDrawable();
    private final GradientDrawable mRawSSoftShade = new GradientDrawable(
            GradientDrawable.Orientation.TOP_BOTTOM, new int[] {0x00000000, 0x48000000});
    private int mRawSCapturedSoftBackingColor;
    private @Nullable WebContents mRawSSoftBackingContents;
    private @Nullable GURL mRawSSoftBackingCommittedUrl;
    private int mRawSSoftBackingWebColor;''')
        edit('''                @Override
                public void onDestroyed(Tab tab) {
                    if (mRawSPageObservedTab''','''                @Override
                public void onBackgroundColorChanged(Tab tab, int color) {
                    if (tab != mRawSPageObservedTab || tab.isNativePage()) return;
                    var contents = tab.getWebContents();
                    if (contents == null || contents.isDestroyed()) return;
                    mRawSSoftBackingContents = contents;
                    mRawSSoftBackingCommittedUrl = contents.getLastCommittedUrl();
                    mRawSSoftBackingWebColor = color;
                    refreshRawSSoftBacking();
                }

                @Override
                public void onDidStartNavigationInPrimaryMainFrame(
                        Tab tab, NavigationHandle navigation) {
                    if (tab == mRawSPageObservedTab && !navigation.isSameDocument()) {
                        clearRawSSoftWebColor();
                        refreshRawSSoftBacking();
                    }
                }

                @Override
                public void onDidFinishNavigationInPrimaryMainFrame(
                        Tab tab, NavigationHandle navigation) {
                    if (tab == mRawSPageObservedTab && navigation.hasCommitted()
                            && !navigation.isSameDocument()) {
                        clearRawSSoftWebColor();
                        refreshRawSSoftBacking();
                    }
                }

                @Override
                public void onContentChanged(Tab tab) {
                    if (tab == mRawSPageObservedTab) {
                        clearRawSSoftWebColor();
                        refreshRawSSoftBacking();
                    }
                }

                @Override
                public void onPageLoadFinished(Tab tab, GURL url) {
                    if (tab == mRawSPageObservedTab) refreshRawSSoftBacking();
                }

                @Override
                public void onDestroyed(Tab tab) {
                    if (mRawSPageObservedTab''')
        edit('''        if (mRawSPageObservedTab != tab) {
            if (mRawSPageObservedTab != null) {''','''        if (mRawSPageObservedTab != tab) {
            clearRawSSoftWebColor();
            if (mRawSPageObservedTab != null) {''')
        edit('''        if (switched) updateRawSCapsuleProgress();''','''        if (switched) {
            updateRawSCapsuleProgress();
            refreshRawSSoftBacking();
        }''')
        edit('''    @Override
    protected void dispatchDraw(Canvas canvas) {
        if (!mTextureCaptureMode && mToolbarBackground.getColor() != Color.TRANSPARENT) {''','''    /** Returns an opaque band color, or transparent when native paint must remain untouched. */
    private @ColorInt int getRawSSoftBackingColor() {
        if (!mRawSPageActionsActive || !canUseRawSPageActions()
                || ChromeFeatureList.sToolbarPhoneAnimationRefactor.isEnabled()
                || mToolbarBackground == null || urlHasFocus()
                || mUrlFocusChangeInProgress || mUrlFocusChangeFraction != 0f
                || mTabSwitcherState != STATIC_TAB || mInLayoutTransition
                || mIsInLoadingPhaseFromNtpToWebpage || mBrandColorTransitionActive
                || isToolbarHairlineSuppressed()
                || mTopPaddingForEdgeToEdgeNtp != 0) {
            return Color.TRANSPARENT;
        }
        var tab = mRawSPageObservedTab;
        if (tab == null) return Color.TRANSPARENT;
        int fallback = mToolbarBackground.getColor();
        if (tab.isNativePage()) {
            // The existing Home wallpaper does not back this reserved band. Use its native base
            // color, never a copied/extended wallpaper bitmap.
            int homeColor = tab.getBackgroundColor();
            return Color.alpha(homeColor) == 255 ? homeColor : fallback | 0xff000000;
        }
        var contents = tab.getWebContents();
        // Tab.getBackgroundColor() can retain the previous document's last color. Only use a
        // positive background event observed for these live contents after the current commit.
        if (!tab.isLoading() && contents != null && contents == mRawSSoftBackingContents
                && !contents.isDestroyed()
                && contents.getLastCommittedUrl().equals(mRawSSoftBackingCommittedUrl)
                && contents.getLastCommittedUrl().equals(tab.getUrl())
                && Color.alpha(mRawSSoftBackingWebColor) == 255) {
            return mRawSSoftBackingWebColor;
        }
        return fallback | 0xff000000;
    }

    private void clearRawSSoftWebColor() {
        mRawSSoftBackingContents = null;
        mRawSSoftBackingCommittedUrl = null;
        mRawSSoftBackingWebColor = Color.TRANSPARENT;
    }

    int getRawSCapturedSoftBackingColor() {
        return mRawSCapturedSoftBackingColor;
    }

    private void refreshRawSSoftBacking() {
        if (!mRawSLegacyCapsuleTrial) return;
        updateHairlineVisibility();
        invalidate();
        if (mLayoutUpdater != null) mLayoutUpdater.run();
    }

    @Override
    protected void dispatchDraw(Canvas canvas) {
        int rawSBackingColor = mTextureCaptureMode ? Color.TRANSPARENT : getRawSSoftBackingColor();
        if (rawSBackingColor != Color.TRANSPARENT) {
            mRawSSoftBacking.setColor(rawSBackingColor);
            mRawSSoftBacking.setBounds(0, 0, getWidth(), getHeight());
            mRawSSoftBacking.draw(canvas);
            mRawSSoftShade.setBounds(0, 0, getWidth(), getHeight());
            mRawSSoftShade.draw(canvas);
        } else if (!mTextureCaptureMode && mToolbarBackground.getColor() != Color.TRANSPARENT) {''')
        edit('''                if (rawSCapsuleProgressChangesCapture()) {
                    snapshotDifference = ToolbarSnapshotDifference.PROGRESS;''','''                if (mRawSCapturedSoftBackingColor != getRawSSoftBackingColor()) {
                    snapshotDifference = ToolbarSnapshotDifference.THEME_COLOR;
                } else if (rawSCapsuleProgressChangesCapture()) {
                    snapshotDifference = ToolbarSnapshotDifference.PROGRESS;''')
        edit('''            if (!hideHairlineForIncognitoNtp()
                    && !hideHairlineForInterstitial()
                    && !hideHairlineForRegularNtpTextureCapture()''','''            mRawSCapturedSoftBackingColor = getRawSSoftBackingColor();
            if (mRawSCapturedSoftBackingColor != Color.TRANSPARENT) {
                getToolbarHairline().setVisibility(INVISIBLE);
            } else if (!hideHairlineForIncognitoNtp()
                    && !hideHairlineForInterstitial()
                    && !hideHairlineForRegularNtpTextureCapture()''')
        edit('''        super.onUrlFocusChange(hasFocus);''','''        super.onUrlFocusChange(hasFocus);
        updateHairlineVisibility();''')
        edit('''        return super.shouldDrawHairline()
                && mTabSwitcherState == STATIC_TAB''','''        return getRawSSoftBackingColor() == Color.TRANSPARENT
                && super.shouldDrawHairline()
                && mTabSwitcherState == STATIC_TAB''')
        edit('''                        mLocationBar.finishUrlFocusChange(hasFocus, shouldShowKeyboard);
                        mUrlFocusChangeInProgress = false;
                    }
                });
        mUrlFocusLayoutAnimator.start();''','''                        mLocationBar.finishUrlFocusChange(hasFocus, shouldShowKeyboard);
                        mUrlFocusChangeInProgress = false;
                        if (mRawSLegacyCapsuleTrial) refreshRawSSoftBacking();
                    }
                });
        mUrlFocusLayoutAnimator.start();''')
        edit('''        mInLayoutTransition = true;
        updateRawSCapsuleProgress();
        updateToolbarBackgroundFromState(mVisualState);''','''        mInLayoutTransition = true;
        updateRawSCapsuleProgress();
        updateToolbarBackgroundFromState(mVisualState);
        refreshRawSSoftBacking();''')
        edit('''        mInLayoutTransition = false;
        mIsInLoadingPhaseFromNtpToWebpage = false;
        updateRawSCapsuleProgress();
        updateToolbarBackgroundFromState(mVisualState);''','''        mInLayoutTransition = false;
        mIsInLoadingPhaseFromNtpToWebpage = false;
        updateRawSCapsuleProgress();
        updateToolbarBackgroundFromState(mVisualState);
        refreshRawSSoftBacking();''')
    elif path == TOOLBAR:
        edit('    void getLocationBarContentRect(Rect outRect);','''    void getLocationBarContentRect(Rect outRect);

    /** Paint metadata from the most recent snapshot; zero means stock backdrop. */
    default int getRawSCapturedSoftBackingColor() {
        return 0;
    }''')
    elif path == COORD:
        edit('''    public int getEdgeToEdgeTopPadding() {
        return mToolbarLayout.getEdgeToEdgeTopPadding();
    }''','''    public int getEdgeToEdgeTopPadding() {
        return mToolbarLayout.getEdgeToEdgeTopPadding();
    }

    @Override
    public int getRawSCapturedSoftBackingColor() {
        return mToolbarLayout instanceof ToolbarPhone phone
                ? phone.getRawSCapturedSoftBackingColor() : 0;
    }''')
    elif path == CONTAINER:
        edit('''                    mToolbarRect, mLocationBarRect, shadowHeight);''','''                    mToolbarRect, mLocationBarRect, shadowHeight,
                    mToolbar.getRawSCapturedSoftBackingColor());''')
    elif path == FACTORY_J:
        edit('''            Rect toolbarPosition, Rect locationBarPosition, int shadowHeight) {
        return ResourceFactoryJni.get()''','''            Rect toolbarPosition, Rect locationBarPosition, int shadowHeight) {
        return createToolbarContainerResource(toolbarPosition, locationBarPosition, shadowHeight, 0);
    }

    public static long createToolbarContainerResource(
            Rect toolbarPosition, Rect locationBarPosition, int shadowHeight,
            int rawSSoftBackingColor) {
        return ResourceFactoryJni.get()''')
        edit('''                        shadowHeight);''','''                        shadowHeight,
                        rawSSoftBackingColor);''')
        edit('''                int shadowHeight);''','''                int shadowHeight,
                int rawSSoftBackingColor);''')
    elif path == FACTORY_C:
        edit('    int32_t shadow_height) {',
             '    int32_t shadow_height,\n    int32_t raws_soft_backing_color) {')
        edit('      toolbar_rect, location_bar_content_rect, shadow_height));',
             '      toolbar_rect, location_bar_content_rect, shadow_height,\n'
             '      raws_soft_backing_color));')
    elif path == RESOURCE_H:
        edit('#include "ui/android/resources/resource.h"',
             '#include <stdint.h>\n\n#include "ui/android/resources/resource.h"')
        edit('                  int shadow_height);',
             '                  int shadow_height,\n                  int32_t raws_soft_backing_color = 0);')
        edit('  int shadow_height() const { return shadow_height_; }',
             '  int shadow_height() const { return shadow_height_; }\n'
             '  int32_t raws_soft_backing_color() const { return raws_soft_backing_color_; }')
        edit('  int shadow_height_;','  int shadow_height_;\n  int32_t raws_soft_backing_color_;')
    elif path == RESOURCE_C:
        edit('                                 int shadow_height)',
             '                                 int shadow_height,\n'
             '                                 int32_t raws_soft_backing_color)')
        edit('      shadow_height_(shadow_height) {}',
             '      shadow_height_(shadow_height),\n'
             '      raws_soft_backing_color_(raws_soft_backing_color) {}')
        edit('      toolbar_rect_, location_bar_content_rect_, shadow_height_);',
             '      toolbar_rect_, location_bar_content_rect_, shadow_height_,\n'
             '      raws_soft_backing_color_);')
    elif path == LAYER_H:
        edit('  scoped_refptr<cc::slim::SolidColorLayer> toolbar_background_layer_;',
             '  scoped_refptr<cc::slim::SolidColorLayer> toolbar_background_layer_;\n'
             '  scoped_refptr<cc::slim::SolidColorLayer> raws_soft_shade_layer_;')
    elif path == LAYER_C:
        edit('#include "ui/gfx/geometry/rounded_corners_f.h"',
             '#include "ui/gfx/geometry/linear_gradient.h"\n'
             '#include "ui/gfx/geometry/rounded_corners_f.h"')
        edit('''  toolbar_background_layer_->SetBackgroundColor(
      SkColor4f::FromColor(toolbar_background_color));''','''  const SkColor raws_soft_backing = resource->raws_soft_backing_color();
  const bool show_raws_soft_shade = SkColorGetA(raws_soft_backing) == 255;
  toolbar_background_layer_->SetBackgroundColor(SkColor4f::FromColor(
      show_raws_soft_shade ? raws_soft_backing : toolbar_background_color));
  if (raws_soft_shade_layer_) {
    raws_soft_shade_layer_->SetHideLayerAndSubtree(!show_raws_soft_shade);
  }
  if (show_raws_soft_shade) {
    if (!raws_soft_shade_layer_) {
      raws_soft_shade_layer_ = cc::slim::SolidColorLayer::Create();
      raws_soft_shade_layer_->SetIsDrawable(true);
      raws_soft_shade_layer_->SetBackgroundColor(SkColors::kBlack);
      // 270 is top-to-bottom in Viz. Same endpoints as the Android draw.
      gfx::LinearGradient mask(270);
      mask.AddStep(0.f, 0);
      mask.AddStep(1.f, 72);
      raws_soft_shade_layer_->SetGradientMask(mask);
      toolbar_background_layer_->AddChild(raws_soft_shade_layer_);
    }
    raws_soft_shade_layer_->SetBounds(resource->toolbar_rect().size());
  }''')
    return text.encode('utf-8')
