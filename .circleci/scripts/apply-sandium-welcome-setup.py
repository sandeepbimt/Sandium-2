#!/usr/bin/env python3
"""Replace Brave promotional first-run pages with Sandium's functional setup UI."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

EXPECTED_CORE_TAG = "v1.98.62"
EXPECTED_CORE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
EXPECTED_CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"

ACTIVITY = Path("android/java/org/chromium/chrome/browser/firstrun/WelcomeOnboardingActivity.java")
JAVA_SOURCES = Path("android/brave_java_sources.gni")
VIEW = Path("android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java")

def read(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"missing pinned source file: {path}")
    return path.read_text(encoding="utf-8")

def write(path: Path, content: str, label: str) -> None:
    # The setup view is a new Sandium-owned file in the pinned Brave checkout.
    # Create its destination tree before checking or writing it.
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")
    if not path.is_file() or path.read_text(encoding="utf-8") != content:
        raise RuntimeError(f"{label}: post-write verification failed")
    print(f"SANDIUM_WELCOME_PATCH={label}:PASS")

def replace_method(source: str, start: str, end: str, replacement: str, label: str) -> str:
    begin = source.find(start)
    if begin < 0:
        if replacement in source:
            return source
        raise RuntimeError(f"{label}: method start anchor missing")
    finish = source.find(end, begin + len(start))
    if finish < 0:
        raise RuntimeError(f"{label}: method end anchor missing")
    existing = source[begin:finish]
    if replacement.strip() in existing:
        return source
    return source[:begin] + replacement + source[finish:]

def replace_once(source: str, old: str, new: str, label: str) -> str:
    if new in source:
        return source
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return source.replace(old, new, 1)

def verify_pins(core: Path, src: Path) -> None:
    tag = subprocess.check_output(
        ["git", "-C", str(core), "describe", "--tags", "--exact-match"], text=True
    ).strip()
    core_sha = subprocess.check_output(
        ["git", "-C", str(core), "rev-parse", "HEAD"], text=True
    ).strip()
    chromium_sha = subprocess.check_output(
        ["git", "-C", str(src), "rev-parse", "HEAD"], text=True
    ).strip()
    if (tag, core_sha, chromium_sha) != (
        EXPECTED_CORE_TAG, EXPECTED_CORE_SHA, EXPECTED_CHROMIUM_SHA
    ):
        raise RuntimeError(
            "SANDIUM_WELCOME_PIN_GATE=FAIL "
            f"expected={EXPECTED_CORE_TAG}@{EXPECTED_CORE_SHA}/{EXPECTED_CHROMIUM_SHA} "
            f"actual={tag}@{core_sha}/{chromium_sha}"
        )
    print(f"SANDIUM_WELCOME_PIN_GATE=PASS brave={tag}@{core_sha} chromium={chromium_sha}")

def transform_activity(source: str) -> str:
    source = replace_once(
        source,
        "    private boolean mSplashAnimationFinished;\n",
        "    private boolean mSplashAnimationFinished;\n"
        "    private @Nullable SandiumWelcomeSetupView mSandiumSetupView;\n",
        "setup-view-field",
    )

    trigger = """    @Override
    public void triggerLayoutInflation() {
        super.triggerLayoutInflation();
        mSandiumSetupView = new SandiumWelcomeSetupView(this, this::finalStep);
        setContentView(mSandiumSetupView.createView());

        checkReferral();
        if (PackageUtils.isFirstInstall(this)) {
            ChromeSharedPreferences.getInstance()
                    .writeBoolean(
                            BravePreferenceKeys.BRAVE_TAB_GROUPS_ENABLED_DEFAULT_VALUE, false);
        }
        onInitialLayoutInflationComplete();
    }

"""
    source = replace_method(
        source,
        "    @Override\n    public void triggerLayoutInflation() {",
        "    @Override\n    public void finishNativeInitialization() {",
        trigger,
        "replace-brave-onboarding-layout",
    )

    finish = """    @Override
    public void finishNativeInitialization() {
        super.finishNativeInitialization();

        mIsP3aManaged = BraveLocalState.get().isManagedPreference(BravePref.P3A_ENABLED);
        mIsCrashReportingManaged =
                !PrivacyPreferencesManagerImpl.getInstance()
                        .isUsageAndCrashReportingPermittedByPolicy();

        // Sandium's first-run defaults are privacy-preserving. Respect enterprise policy.
        if (!mIsP3aManaged) {
            setP3aConsent(false);
        }
        if (!mIsCrashReportingManaged) {
            setMetricsReportingConsent(false, false);
        }

        org.chromium.chrome.browser.profiles.Profile profile =
                assumeNonNull(getProfileProviderSupplier().get()).getOriginalProfile();
        assumeNonNull(mSandiumSetupView).initialize(profile);
    }

"""
    source = replace_method(
        source,
        "    @Override\n    public void finishNativeInitialization() {",
        "    @Override\n    protected void onSaveInstanceState(Bundle outState) {",
        finish,
        "preserve-first-run-native-initialization",
    )

    save = """    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
    }

"""
    source = replace_method(
        source,
        "    @Override\n    protected void onSaveInstanceState(Bundle outState) {",
        "    @Override\n    protected void onRestoreInstanceState(Bundle state) {",
        save,
        "remove-obsolete-pager-state",
    )

    promo = """        ChromeSharedPreferences.getInstance()
                .writeBoolean(OnboardingPrefManager.SHOULD_SHOW_SEARCH_WIDGET_PROMO, true);
"""
    if promo in source:
        source = source.replace(promo, "", 1)

    destroy = """    @Override
    protected void onDestroy() {
        if (mSandiumSetupView != null) {
            mSandiumSetupView.destroy();
        }
        super.onDestroy();
    }

"""
    if "protected void onDestroy()" not in source:
        anchor = "    @Override\n    public @BackPressResult int handleBackPress() {"
        source = replace_once(source, anchor, destroy + anchor, "setup-view-lifecycle")
    elif "mSandiumSetupView.destroy();" not in source:
        raise RuntimeError("existing onDestroy must be reviewed before adding setup cleanup")

    required = (
        "new SandiumWelcomeSetupView(this, this::finalStep)",
        "assumeNonNull(mSandiumSetupView).initialize(profile)",
        "setP3aConsent(false)",
        "setMetricsReportingConsent(false, false)",
        "FirstRunStatus.setFirstRunFlowComplete(true)",
        "FirstRunUtils.setEulaAccepted()",
        "mSandiumSetupView.destroy()",
    )
    missing = [item for item in required if item not in source]
    if missing:
        raise RuntimeError("welcome activity verification missing: " + ", ".join(missing))
    if "SHOULD_SHOW_SEARCH_WIDGET_PROMO, true" in source:
        raise RuntimeError("Brave search-widget promotion must not be queued by Sandium first-run")
    return source

def transform_java_sources(source: str) -> str:
    entry = '  "../../brave/android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java",\n'
    anchor = '  "../../brave/android/java/org/chromium/chrome/browser/firstrun/WelcomeOnboardingActivity.java",\n'
    if entry in source:
        return source
    if source.count(anchor) != 1:
        raise RuntimeError("brave_java_sources.gni: expected exactly one WelcomeOnboardingActivity entry")
    return source.replace(anchor, anchor + entry, 1)

def apply(core: Path, src: Path, repo_root: Path) -> None:
    verify_pins(core, src)
    activity_path = core / ACTIVITY
    source_list_path = core / JAVA_SOURCES
    view_source = read(repo_root / VIEW)
    required_view_behaviour = (
        "sandium.ad_block.engine_warmup_done_v2",
        "REQUIRED_FILTER_COUNT = 29",
        "downloaded == REQUIRED_FILTER_COUNT",
        'Arrays.asList("Off", "Low", "Medium", "High")',
        "mDarkenSwitch.setEnabled(!off)",
        "BraveRelaunchUtils.restart()",
    )
    if "class SandiumWelcomeSetupView" not in view_source:
        raise RuntimeError("Sandium setup view class missing from repository workspace")
    missing_view_behaviour = [
        marker for marker in required_view_behaviour if marker not in view_source
    ]
    if missing_view_behaviour:
        raise RuntimeError(
            "welcome view verification missing required behavior: "
            + ", ".join(missing_view_behaviour)
        )
    write(core / VIEW, view_source, "welcome-setup-view")
    write(activity_path, transform_activity(read(activity_path)), "welcome-activity")
    write(source_list_path, transform_java_sources(read(source_list_path)), "java-source-registration")
    print("SANDIUM_WELCOME_SETUP_VERIFY=PASS brand_neutral=true expanded_more_options=true "
          "engine_ready_gated_continue=true preserve_eula=true preserve_install_referrer=true "
          "suppress_brave_promotions=true")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--src", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()
    apply(args.core, args.src, args.repo_root)

if __name__ == "__main__":
    main()
