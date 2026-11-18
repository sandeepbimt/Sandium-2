"""Dormant exact-source layout eligibility hook. Not in the active plan."""
from pathlib import Path
LAYOUT = "chrome/android/java/src/org/chromium/chrome/browser/compositor/layouts/Layout.java"
STATIC = "chrome/android/java/src/org/chromium/chrome/browser/compositor/layouts/StaticLayout.java"
MARKER = "SANDIUM_NATIVE_HANDOFF_SCENE_ELIGIBILITY_V1"
SIGNATURE = """    public boolean isSandiumNativeHandoffSceneEligible(
            @Nullable Tab expectedTab,
            @Nullable WebContents expectedWebContents,
            @Nullable SceneLayer selectedScene)"""
DEFAULT = """    // SANDIUM_NATIVE_HANDOFF_SCENE_ELIGIBILITY_V1
    // Unknown layouts are never admitted. Pure query, safe to repeat at delivery.
""" + SIGNATURE + """ {
        return false;
    }

"""
OVERRIDE = """    // SANDIUM_NATIVE_HANDOFF_SCENE_ELIGIBILITY_V1
    // Selection/ownership only, NOT presentation, occlusion or control stability.
    @Override
""" + SIGNATURE + """ {
        if (expectedTab == null || expectedWebContents == null || selectedScene == null
                || mSceneLayer == null || selectedScene != mSceneLayer
                || mTabModelSelector == null || !isActive() || !mIsShowing
                || getLayoutType() != LayoutType.BROWSING
                || isStartingToHide() || isStartingToShow() || isRunningAnimations()
                || !mModel.get(LayoutTab.IS_ACTIVE_LAYOUT)
                || mModel.get(LayoutTab.SCALE) != 1.0f
                || mModel.get(LayoutTab.X) != 0.0f || mModel.get(LayoutTab.Y) != 0.0f
                || mModel.get(LayoutTab.RENDER_X) != 0.0f
                || mModel.get(LayoutTab.RENDER_Y) != 0.0f) return false;
        Tab currentTab = mTabModelSelector.getCurrentTab();
        if (currentTab != expectedTab || currentTab.isDestroyed() || currentTab.isHidden()
                || currentTab.getId() == Tab.INVALID_TAB_ID
                || mModel.get(LayoutTab.TAB_ID) != currentTab.getId()
                || !mModel.get(LayoutTab.CAN_USE_LIVE_TEXTURE)
                || currentTab.getWebContents() != expectedWebContents
                || expectedWebContents.isDestroyed()
                || currentTab.isNativePage() || SadTab.isShowing(currentTab)
                || currentTab.isDisplayingBackForwardAnimation()) return false;
        String scheme = currentTab.getUrl().getScheme();
        return "https".equals(scheme) || "http".equals(scheme);
    }

"""
def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Pinned eligibility anchor drift: " + old[:80])
    return text.replace(old, new, 1)
def transform(path, text):
    if path not in (LAYOUT, STATIC):
        raise ValueError("Unknown eligibility source: " + path)
    if MARKER in text:
        expected = DEFAULT if path == LAYOUT else OVERRIDE
        if text.count(MARKER) != 1 or expected not in text:
            raise ValueError("Partial eligibility overlay")
        return text
    if path == LAYOUT:
        text = once(text, "import org.chromium.chrome.browser.tab.Tab;",
            "import org.chromium.chrome.browser.tab.Tab;\nimport org.chromium.content_public.browser.WebContents;")
        return once(text, "    public abstract @LayoutType int getLayoutType();",
            DEFAULT + "    public abstract @LayoutType int getLayoutType();")
    anchor = "    @Override\n    public int getLayoutType() {\n        return LayoutType.BROWSING;\n    }"
    return once(text, anchor, OVERRIDE + anchor)
def plan(root):
    root = Path(root)
    return {root / p: transform(p, (root / p).read_text()) for p in (LAYOUT, STATIC)}
