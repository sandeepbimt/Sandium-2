#!/usr/bin/env python3
"""Apply the Sandium Android brand refresh to the pinned Brave/Chromium source."""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
from pathlib import Path

EXPECTED_CORE_TAG = "v1.98.62"
EXPECTED_CORE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
EXPECTED_CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"

ASSETS = {
    "icon.webp": "dbddd3838a9995ead3ef456a8ab964b7142e4c255232f1e27daf57572a73b3fe",
    "logo-mark.webp": "1f2f20b55c3a1d1ccdcaed4024eb88b31e9b763d5d63b73b68727f1247b127c2",
    "wallpaper.webp": "6f4e5c7ca70a0b0c69ab27874b7a878a9c8a98de34fee706b24a06f8af5ed842",
}

def read(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"required source file is missing: {path}")
    return path.read_text(encoding="utf-8")

def write(path: Path, content: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")
    if path.read_text(encoding="utf-8") != content:
        raise RuntimeError(f"{label}: post-write verification failed")
    print(f"SANDIUM_BRANDING_PATCH={label}:PASS")

def replace_once(path: Path, old: str, new: str, label: str) -> None:
    source = read(path)
    if new in source:
        print(f"SANDIUM_BRANDING_PATCH={label}:ALREADY_APPLIED")
        return
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one source anchor, found {count}: {path}")
    write(path, source.replace(old, new, 1), label)

def replace_application_label(path: Path, label: str) -> None:
    """Set the app label while tolerating harmless Jinja/attribute formatting changes."""
    source = read(path)
    application = re.search(r"<application\b[^>]*>", source, re.DOTALL)
    if application is None:
        raise RuntimeError(f"application-label: <application> element not found: {path}")

    tag = application.group(0)
    pattern = re.compile(r'(\bandroid:label\s*=\s*")[^"]*(")', re.DOTALL)
    matches = list(pattern.finditer(tag))
    if len(matches) != 1:
        raise RuntimeError(
            "application-label: expected one android:label attribute in <application>, "
            f"found {len(matches)}: {path}"
        )

    match = matches[0]
    current = match.group(0)
    value = current[len(match.group(1)):-len(match.group(2))]
    if "{% block application_label %}" in value and "{% endblock %}" in value:
        desired_value = "{% block application_label %}" + label + "{% endblock %}"
    else:
        desired_value = label
    replacement = match.group(1) + desired_value + match.group(2)

    if current == replacement:
        print("SANDIUM_BRANDING_PATCH=application-label:ALREADY_APPLIED")
        return

    updated_tag = tag[:match.start()] + replacement + tag[match.end():]
    updated = source[:application.start()] + updated_tag + source[application.end():]
    write(path, updated, "application-label")

def replace_android_icon_item(path: Path, element: str, drawable: str, label: str) -> None:
    """Set one adaptive-icon element regardless of the checkpoint's prior drawable."""
    source = read(path)
    pattern = re.compile(r"<" + re.escape(element) + r"\b[^>]*/>")
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise RuntimeError(
            f"{label}: expected one <{element}> element, found {len(matches)}: {path}"
        )
    replacement = f'<{element} android:drawable="{drawable}"/>'
    if matches[0].group(0) == replacement:
        print(f"SANDIUM_BRANDING_PATCH={label}:ALREADY_APPLIED")
        return
    updated = source[:matches[0].start()] + replacement + source[matches[0].end():]
    write(path, updated, label)

def remove_once(path: Path, old: str, label: str) -> None:
    source = read(path)
    if old not in source:
        print(f"SANDIUM_BRANDING_PATCH={label}:ALREADY_APPLIED")
        return
    if source.count(old) != 1:
        raise RuntimeError(f"{label}: expected one import to remove, found {source.count(old)}")
    write(path, source.replace(old, "", 1), label)

def add_gn_source(path: Path, anchor: str, addition: str, label: str) -> None:
    source = read(path)
    if addition in source:
        print(f"SANDIUM_BRANDING_PATCH={label}:ALREADY_APPLIED")
        return
    count = source.count(anchor)
    if count < 1:
        raise RuntimeError(f"{label}: GN anchor missing")
    # Chromium lists shared base resources in both the base-module and
    # override-module targets; register the new assets in every matching list.
    write(path, source.replace(anchor, anchor + addition), label)

def git_value(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

def verify_pins(core: Path, src: Path) -> None:
    actual_tag = git_value(core, "describe", "--tags", "--exact-match")
    actual_core = git_value(core, "rev-parse", "HEAD")
    actual_chromium = git_value(src, "rev-parse", "HEAD")
    expected = (EXPECTED_CORE_TAG, EXPECTED_CORE_SHA, EXPECTED_CHROMIUM_SHA)
    actual = (actual_tag, actual_core, actual_chromium)
    if actual != expected:
        raise RuntimeError(
            "SANDIUM_BRANDING_PIN_GATE=FAIL "
            f"expected={expected!r} actual={actual!r}"
        )
    print(
        "SANDIUM_BRANDING_PIN_GATE=PASS "
        f"brave={actual_tag}@{actual_core} chromium={actual_chromium}"
    )

def install_asset(source_dir: Path, name: str, destination: Path) -> None:
    source = source_dir / name
    if not source.is_file():
        raise RuntimeError(f"missing official Sandium asset: {source}")
    payload = source.read_bytes()
    if payload[:4] != b"RIFF" or payload[8:12] != b"WEBP":
        raise RuntimeError(f"asset is not a valid WebP: {source}")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != ASSETS[name]:
        raise RuntimeError(f"asset checksum mismatch for {name}: {digest}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.is_file() or destination.read_bytes() != payload:
        shutil.copyfile(source, destination)
    if destination.read_bytes() != payload:
        raise RuntimeError(f"asset copy verification failed: {destination}")
    print(f"SANDIUM_BRANDING_ASSET={name}:PASS sha256={digest}")

def replace_toolbar_method(core: Path) -> None:
    path = core / "android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java"
    source = read(path)
    start = "    private void setRewardsLayoutVisibility(int visibility) {"
    applied_start = "    private void setRewardsLayoutVisibility(int requestedVisibility) {"
    end = "    private void requestToolbarSnapshotCapture() {"
    replacement = """    private void setRewardsLayoutVisibility(int requestedVisibility) {
        if (mRewardsLayout == null || mRewardsLayout.getVisibility() == View.GONE) {
            return;
        }
        // Sandium hides only the toolbar affordance. Rewards services, settings,
        // native components and policy handling remain intact.
        mRewardsLayout.setVisibility(View.GONE);
        updateShieldsLayoutBackground(true);
        if (BraveReflectionUtil.equalTypes(this.getClass(), ToolbarTablet.class)) {
            post(mRewardsLayout::requestLayout);
            invalidateToolbarSnapshotOnTablet();
        }
    }

"""
    if applied_start in source:
        # The first replacement changes the parameter name. Recognize that exact
        # post-patch signature before looking for the original anchor, so cache-
        # restored and retried stages remain safe to execute.
        if source.count(applied_start) != 1:
            raise RuntimeError("toolbar Rewards visibility replacement is not unique")
        begin = source.find(applied_start)
        finish = source.find(end, begin + len(applied_start))
        if finish < 0:
            raise RuntimeError("toolbar Rewards visibility replacement end anchor changed")
        method = source[begin:finish]
        required = (
            "mRewardsLayout == null || mRewardsLayout.getVisibility() == View.GONE",
            "mRewardsLayout.setVisibility(View.GONE);",
            "updateShieldsLayoutBackground(true);",
            "invalidateToolbarSnapshotOnTablet();",
        )
        missing = [anchor for anchor in required if anchor not in method]
        if missing:
            raise RuntimeError(
                "toolbar Rewards visibility replacement is incomplete; "
                f"review before continuing: {missing!r}"
            )
        print("SANDIUM_BRANDING_PATCH=hide-toolbar-rewards:ALREADY_APPLIED")
    else:
        begin = source.find(start)
        if begin < 0:
            raise RuntimeError("toolbar Rewards visibility method anchors changed")
        finish = source.find(end, begin + len(start))
        if finish < 0:
            raise RuntimeError("toolbar Rewards visibility method end anchor changed")
        write(path, source[:begin] + replacement + source[finish:], "hide-toolbar-rewards")

    source = read(path)
    start = "    public void updateBraveShieldsButtonState(Tab tab) {"
    end = "    private boolean isShieldsOnForTab(Tab tab) {"
    begin = source.find(start)
    finish = source.find(end, begin + len(start))
    if begin < 0 or finish < 0:
        raise RuntimeError("toolbar Shields state method anchors changed")
    replacement = """    public void updateBraveShieldsButtonState(Tab tab) {
        if (mBraveShieldsButton == null) {
            assert false;
            return;
        }

        // Keep Brave's original state semantics: null-tab and Shields-off states
        // are subdued; a real tab with Shields enabled uses the full-strength mark.
        boolean shieldsEnabled = tab != null && isShieldsOnForTab(tab);
        android.graphics.drawable.Drawable current = mBraveShieldsButton.getDrawable();
        SandiumShieldsTracer tracer;
        if (current instanceof SandiumShieldsTracer) {
            tracer = (SandiumShieldsTracer) current;
        } else {
            tracer = new SandiumShieldsTracer(mBraveShieldsButton);
            mBraveShieldsButton.setImageDrawable(tracer);
        }
        mBraveShieldsButton.setImageAlpha(shieldsEnabled ? 255 : 112);
        tracer.setEnabled(shieldsEnabled);

        // Hide only the toolbar Rewards/BAT view. Do not disable the Rewards backend.
        setRewardsLayoutVisibility(View.GONE);
        updateShieldsLayoutBackground(true);
    }

"""
    replacement += """    /** Balanced tracer, sampled from the verified 64 x 77 logo alpha silhouette. */
    private static final class SandiumShieldsTracer extends android.graphics.drawable.Drawable
            implements Runnable, View.OnAttachStateChangeListener,
                    android.view.ViewTreeObserver.OnWindowFocusChangeListener,
                    android.view.ViewTreeObserver.OnGlobalLayoutListener {
        private final android.widget.ImageView mHost;
        private final android.graphics.drawable.Drawable mMark;
        private final android.graphics.Path mOutline = new android.graphics.Path();
        private final android.graphics.Path mScaled = new android.graphics.Path();
        private final android.graphics.Path mSegment = new android.graphics.Path();
        private final android.graphics.PathMeasure mMeasure = new android.graphics.PathMeasure();
        private final android.graphics.Paint mPaint =
                new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        private final android.graphics.Matrix mMatrix = new android.graphics.Matrix();
        private final float[] mImageMatrixValues = new float[9];
        private boolean mEnabled;
        private boolean mListening;
        private int mAlpha = 255;
        private final long mEpoch = android.os.SystemClock.uptimeMillis();

        SandiumShieldsTracer(android.widget.ImageView host) {
            mHost = host;
            mMark = host.getContext().getDrawable(R.drawable.sandium_toolbar_mark).mutate();
            mPaint.setStyle(android.graphics.Paint.Style.STROKE);
            mPaint.setStrokeCap(android.graphics.Paint.Cap.ROUND);
            mPaint.setStrokeJoin(android.graphics.Paint.Join.ROUND);
            mPaint.setColor(0xFF46C878);
            mPaint.setStrokeWidth(2.0f * host.getResources().getDisplayMetrics().density);
            android.graphics.Path outline = mOutline;
            outline.moveTo(44.50f, 0.40f);
            outline.lineTo(49.50f, 0.04f);
            outline.lineTo(54.50f, 2.15f);
            outline.lineTo(59.87f, 7.50f);
            outline.lineTo(62.04f, 11.50f);
            outline.lineTo(61.69f, 12.50f);
            outline.lineTo(28.11f, 29.50f);
            outline.lineTo(29.50f, 30.11f);
            outline.lineTo(32.50f, 28.27f);
            outline.lineTo(34.50f, 28.42f);
            outline.lineTo(57.50f, 35.99f);
            outline.lineTo(62.64f, 41.50f);
            outline.lineTo(63.66f, 46.50f);
            outline.lineTo(62.65f, 51.50f);
            outline.lineTo(59.76f, 55.50f);
            outline.lineTo(56.50f, 57.85f);
            outline.lineTo(20.50f, 75.81f);
            outline.lineTo(15.50f, 76.93f);
            outline.lineTo(10.50f, 75.80f);
            outline.lineTo(4.95f, 71.50f);
            outline.lineTo(0.96f, 64.50f);
            outline.lineTo(30.52f, 49.50f);
            outline.lineTo(29.50f, 48.40f);
            outline.lineTo(8.50f, 41.70f);
            outline.lineTo(4.84f, 39.50f);
            outline.lineTo(2.04f, 36.50f);
            outline.lineTo(0.03f, 31.50f);
            outline.lineTo(1.36f, 24.50f);
            outline.lineTo(6.50f, 18.99f);
            outline.lineTo(44.50f, 0.40f);
            outline.close();
            host.addOnAttachStateChangeListener(this);
            if (host.isAttachedToWindow()) onViewAttachedToWindow(host);
        }

        void setEnabled(boolean enabled) {
            mEnabled = enabled;
            refresh();
        }

        private boolean canAnimate() {
            return mEnabled && mHost.isAttachedToWindow() && mHost.isShown()
                    && mHost.hasWindowFocus() && isVisible()
                    && android.animation.ValueAnimator.areAnimatorsEnabled();
        }

        private void refresh() {
            unscheduleSelf(this);
            invalidateSelf();
            if (canAnimate()) scheduleSelf(this, android.os.SystemClock.uptimeMillis() + 33);
        }

        @Override
        public void run() { refresh(); }

        @Override
        protected void onBoundsChange(android.graphics.Rect bounds) {
            mMark.setBounds(bounds);
            mMatrix.setRectToRect(new android.graphics.RectF(0, 0, 64, 77),
                    new android.graphics.RectF(bounds), android.graphics.Matrix.ScaleToFit.FILL);
            mOutline.transform(mMatrix, mScaled);
            mMeasure.setPath(mScaled, true);
        }

        @Override
        public void draw(android.graphics.Canvas canvas) {
            mMark.draw(canvas);
            if (!mEnabled) return;
            // ImageView applies its own image matrix; compensate so the final
            // stroke remains 2dp rather than 2 raster pixels.
            mHost.getImageMatrix().getValues(mImageMatrixValues);
            float scale = Math.abs(mImageMatrixValues[android.graphics.Matrix.MSCALE_X]);
            mPaint.setStrokeWidth(2.0f * mHost.getResources().getDisplayMetrics().density
                    / Math.max(0.01f, scale));
            mPaint.setAlpha(mAlpha * 220 / 255);
            float length = mMeasure.getLength();
            float phase = android.animation.ValueAnimator.areAnimatorsEnabled()
                    ? ((android.os.SystemClock.uptimeMillis() - mEpoch) % 3200L) / 3200.0f : 0.0f;
            float start = length * phase;
            float end = start + length * 0.35f;
            mSegment.rewind();
            mMeasure.getSegment(start, Math.min(end, length), mSegment, true);
            if (end > length) mMeasure.getSegment(0, end - length, mSegment, true);
            canvas.drawPath(mSegment, mPaint);
        }

        @Override
        public boolean setVisible(boolean visible, boolean restart) {
            boolean changed = super.setVisible(visible, restart);
            refresh();
            return changed;
        }

        @Override
        public void setAlpha(int alpha) {
            mAlpha = alpha;
            mMark.setAlpha(alpha);
            invalidateSelf();
        }

        @Override
        public void setColorFilter(android.graphics.ColorFilter filter) {
            // Keep the original logo and green accent independent of toolbar tint.
        }

        @Override
        public int getOpacity() { return android.graphics.PixelFormat.TRANSLUCENT; }
        @Override
        public int getIntrinsicWidth() { return mMark.getIntrinsicWidth(); }
        @Override
        public int getIntrinsicHeight() { return mMark.getIntrinsicHeight(); }
        @Override
        public void onWindowFocusChanged(boolean focused) { refresh(); }
        @Override
        public void onGlobalLayout() { refresh(); }
        @Override
        public void onViewAttachedToWindow(View view) {
            if (!mListening) {
                view.getViewTreeObserver().addOnWindowFocusChangeListener(this);
                view.getViewTreeObserver().addOnGlobalLayoutListener(this);
                mListening = true;
            }
            refresh();
        }
        @Override
        public void onViewDetachedFromWindow(View view) {
            unscheduleSelf(this);
            if (view.getViewTreeObserver().isAlive()) {
                view.getViewTreeObserver().removeOnWindowFocusChangeListener(this);
                view.getViewTreeObserver().removeOnGlobalLayoutListener(this);
            }
            mListening = false;
        }
    }

"""
    method = source[begin:finish]
    if method == replacement:
        print("SANDIUM_BRANDING_PATCH=toolbar-shields-mark:ALREADY_APPLIED")
    else:
        write(path, source[:begin] + replacement + source[finish:], "toolbar-shields-mark")

def apply(args: argparse.Namespace) -> None:
    core = args.core.resolve()
    src = args.src.resolve()
    root = args.repo_root.resolve()
    verify_pins(core, src)

    source_dir = root / ".circleci/branding/source"
    install_asset(source_dir, "icon.webp",
                  src / "chrome/android/java/res_chromium_base/mipmap-nodpi/sandium_app_icon.webp")
    install_asset(source_dir, "logo-mark.webp",
                  src / "chrome/android/java/res_chromium_base/drawable-nodpi/sandium_themed_app_icon.webp")
    install_asset(source_dir, "logo-mark.webp",
                  core / "android/java/brave-res/drawable-nodpi/sandium_toolbar_mark.webp")
    install_asset(source_dir, "wallpaper.webp",
                  core / "android/java/brave-res/drawable-nodpi/sandium_wallpaper.webp")

    chrome_build = src / "chrome/android/BUILD.gn"
    # The inset drawable belongs to the base module's res_base directory.
    # Do not add it to chrome_public_apk_base_module_resources: that overlay
    # target only owns res_chromium_base, and mixing res_base causes its
    # resource source-list check to reject the other base-module resources.
    add_gn_source(
        chrome_build,
        '      "java/res_base/drawable/ic_launcher.xml",\n',
        '      "java/res_base/drawable/sandium_app_icon_inset.xml",\n',
        "register-chromium-base-module-brand-icon",
    )
    # These res_chromium_base assets are shared by the base and public APK
    # override targets, so register them in both matching GN source lists.
    add_gn_source(
        chrome_build,
        '      "java/res_chromium_base/drawable/themed_app_icon.xml",\n',
        '      "java/res_chromium_base/drawable-nodpi/sandium_themed_app_icon.webp",\n'
        '      "java/res_chromium_base/mipmap-nodpi/sandium_app_icon.webp",\n',
        "register-chromium-brand-assets",
    )
    brave_build = core / "android/BUILD.gn"
    add_gn_source(
        brave_build,
        '    "java/brave-res/drawable-nodpi/dylan_malval_sea_min.webp",\n',
        '    "java/brave-res/drawable-nodpi/sandium_toolbar_mark.webp",\n'
        '    "java/brave-res/drawable-nodpi/sandium_wallpaper.webp",\n',
        "register-brave-brand-assets",
    )

    launcher = src / "chrome/android/java/res_base/drawable/ic_launcher.xml"
    replace_android_icon_item(launcher, "background", "@android:color/black", "launcher-background")
    inset_drawable = src / "chrome/android/java/res_base/drawable/sandium_app_icon_inset.xml"
    write(
        inset_drawable,
        """<?xml version="1.0" encoding="utf-8"?>
<inset xmlns:android="http://schemas.android.com/apk/res/android"
    android:drawable="@mipmap/sandium_app_icon"
    android:inset="8%" />
""",
        "launcher-icon-inset",
    )
    replace_android_icon_item(launcher, "foreground", "@drawable/sandium_app_icon_inset", "launcher-foreground")
    replace_android_icon_item(launcher, "monochrome", "@drawable/sandium_themed_app_icon", "launcher-monochrome")

    launcher_round = src / "chrome/android/java/res_base/drawable/ic_launcher_round.xml"
    replace_android_icon_item(launcher_round, "background", "@android:color/black", "round-launcher-background")
    replace_android_icon_item(launcher_round, "foreground", "@drawable/sandium_app_icon_inset", "round-launcher-foreground")
    replace_android_icon_item(launcher_round, "monochrome", "@drawable/sandium_themed_app_icon", "round-launcher-monochrome")
    replace_application_label(
        src / "chrome/android/java/AndroidManifest.xml",
        "Sandium",
    )

    toolbar_xml = core / "android/java/brave-res/layout/brave_toolbar.xml"
    # Remove the previous duplicate/blur layer on restored checkpoints. The
    # tracer shares the button's drawable bounds, so it cannot drift off the S.
    toolbar_source = read(toolbar_xml)
    toolbar_source, removed = re.subn(
        r'      <ImageView android:id="@\+id/sandium_shields_glow"\s[^>]*?/>\n',
        "", toolbar_source, flags=re.DOTALL)
    if removed > 1:
        raise RuntimeError("duplicate Sandium glow layers")
    if removed:
        write(toolbar_xml, toolbar_source, "remove-toolbar-shields-glow")
    replace_once(
        toolbar_xml,
        'android:src="@drawable/ic_social_brave_release_favicon_fullheight_color"',
        'android:src="@drawable/sandium_toolbar_mark"',
        "toolbar-layout-mark",
    )
    custom_tabs_xml = core / "android/java/brave-res/layout/brave_custom_tabs_toolbar.xml"
    replace_once(
        custom_tabs_xml,
        'android:src="@drawable/ic_social_brave_release_favicon_fullheight_color"',
        'android:src="@drawable/sandium_toolbar_mark"',
        "custom-tabs-toolbar-mark",
    )
    replace_toolbar_method(core)

    strings = core / "browser/ui/android/strings/android_brave_strings.grd"

    sponsored = core / "android/java/org/chromium/chrome/browser/ntp_background_images/util/SponsoredContentUtil.java"
    remove_once(
        sponsored,
        "import org.chromium.chrome.browser.ntp_background_images.model.ImageCredit;",
        "remove-unused-wallpaper-credit-import",
    )
    replace_once(
        sponsored,
        """    private static final List<BackgroundImage> sBackgroundImages =
            new ArrayList<BackgroundImage>(
                    Arrays.asList(
                            new BackgroundImage(
                                    R.drawable.dylan_malval_sea_min,
                                    1300,
                                    720,
                                    new ImageCredit(
                                            "Dylan Malval",
                                            "https://www.instagram.com/vass_captures/"))));
""",
        """    private static final List<BackgroundImage> sBackgroundImages =
            new ArrayList<BackgroundImage>(
                    Arrays.asList(new BackgroundImage(R.drawable.sandium_wallpaper, 270, 480)));
""",
        "ntp-default-wallpaper",
    )

    bridge = core / "android/java/org/chromium/chrome/browser/ntp_background_images/NTPBackgroundImagesBridge.java"
    bridge_source = read(bridge)
    if "import org.chromium.base.ContextUtils;" not in bridge_source:
        bridge_source = bridge_source.replace(
            "import org.chromium.base.Callback;\n",
            "import org.chromium.base.Callback;\nimport org.chromium.base.ContextUtils;\n",
            1,
        )
        write(bridge, bridge_source, "wallpaper-resource-context-import")
    if "import org.chromium.chrome.R;" not in bridge_source:
        bridge_source = bridge_source.replace(
            "import org.chromium.base.ThreadUtils;\n",
            "import org.chromium.base.ThreadUtils;\n\nimport org.chromium.chrome.R;\n",
            1,
        )
    if bridge_source != read(bridge):
        write(bridge, bridge_source, "wallpaper-resource-imports")
    remove_once(
        bridge,
        "import org.chromium.chrome.browser.ntp_background_images.model.ImageCredit;",
        "remove-unused-wallpaper-credit-import",
    )
    replace_once(
        bridge,
        """    public static BackgroundImage createWallpaper(String imagePath, String author, String link) {
        return new BackgroundImage(imagePath, 0, 0, new ImageCredit(author, link));
    }
""",
        """    public static BackgroundImage createWallpaper(String imagePath, String author, String link) {
        return new BackgroundImage(R.drawable.sandium_wallpaper, 270, 480);
    }
""",
        "normal-wallpaper-callback",
    )
    replace_once(
        bridge,
        """        // The metricType int value can be passed directly since @IntDef just validates the value
        return new Wallpaper(
                imagePath,
                focalPointX,
                focalPointY,
                logoPath,
                logoDestinationUrl,
                isSponsored,
                creativeInstanceId,
                wallpaperId,
                isRichMedia,
                metricType);
""",
        """        // Replace remote/branded artwork with the bundled Sandium wallpaper while
        // preserving the callback contract and using the installed app's resource URI.
        String resourceUri =
                "android.resource://"
                        + ContextUtils.getApplicationContext().getPackageName()
                        + "/drawable/sandium_wallpaper";
        return new Wallpaper(
                resourceUri,
                focalPointX,
                focalPointY,
                null,
                "",
                false,
                "",
                "",
                false,
                metricType);
""",
        "branded-wallpaper-callback",
    )

    image_util = core / "android/java/org/chromium/chrome/browser/ntp_background_images/util/NTPImageUtil.java"
    replace_once(
        image_util,
        '        Uri imageFileUri = Uri.parse("file://" + imagePath);',
        '        Uri imageFileUri = imagePath.startsWith("android.resource://")\n'
        '                ? Uri.parse(imagePath)\n'
        '                : Uri.parse("file://" + imagePath);',
        "android-resource-wallpaper-uri",
    )

    ntp_layout = core / "android/java/org/chromium/chrome/browser/ntp/BraveNewTabPageLayout.java"
    replace_once(
        ntp_layout,
        """                && mNtpImageGlobal instanceof Wallpaper
                && getTab() != null
""",
        """                && mNtpImageGlobal instanceof Wallpaper
                && ((Wallpaper) mNtpImageGlobal).isSponsored()
                && getTab() != null
""",
        "sponsored-infobar-guard",
    )

    # The pinned Brave source already registers this preference as true. Do not
    # write a profile preference here: existing users' explicit setting is preserved.
    pref_registry = core / "components/ntp_background_images/common/view_counter_pref_registry.cc"
    pref_source = read(pref_registry)
    if "RegisterBooleanPref(prefs::kNewTabPageShowBackgroundImage, true);" not in pref_source:
        raise RuntimeError("fresh-profile wallpaper default is no longer true; review before changing")
    print("SANDIUM_BRANDING_NTP_DEFAULT=PASS fresh_profile=true user_override=preserved")
    print("SANDIUM_BRANDING_GATE=PASS mode=android-resource-java")
    
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--src", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    apply(parser.parse_args())

if __name__ == "__main__":
    main()
