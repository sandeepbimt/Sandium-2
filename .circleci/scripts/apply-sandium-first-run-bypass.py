#!/usr/bin/env python3
"""Apply Sandium's privacy-safe, no-promotion first-run flow to pinned Brave Core."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

EXPECTED_BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
EXPECTED_BRAVE_TAG = "v1.98.62"
MARKER = "SANDIUM_FIRST_RUN_BYPASS_V1"

ACTIVITY_RELATIVE = Path(
    "android/java/org/chromium/chrome/browser/firstrun/WelcomeOnboardingActivity.java"
)
ADAPTER_RELATIVE = Path(
    "browser/first_run/android/java/src/org/chromium/chrome/browser/firstrun/OnboardingStepAdapter.java"
)

TRIGGER_START = "    @Override\n    public void triggerLayoutInflation() {"
TRIGGER_END = "\n    @Override\n    public void finishNativeInitialization()"
FINISH_START = "    @Override\n    public void finishNativeInitialization() {"
FINISH_END = "\n    private void playAnimatedVectorDrawable()"

TRIGGER_REPLACEMENT = """    @Override
    public void triggerLayoutInflation() {
        super.triggerLayoutInflation();
        setContentView(R.layout.activity_welcome_onboarding);

        // SANDIUM_FIRST_RUN_BYPASS_V1: keep the activity lifecycle, but never render
        // Brave's splash, promotional cards, or onboarding pager.
        mOnboardingPager = findViewById(R.id.onboarding_steps_pager);
        mOnboardingPager.setVisibility(View.GONE);

        mBraveSplash = findViewById(R.id.brave_splash);
        mBraveSplash.setVisibility(View.GONE);
        mBraveSplashContainer = findViewById(R.id.brave_splash_container);
        if (mBraveSplashContainer != null) {
            mBraveSplashContainer.setVisibility(View.GONE);
        }

        // Preserve install-referrer/deep-link handling and the first-install default.
        checkReferral();
        if (PackageUtils.isFirstInstall(this)) {
            ChromeSharedPreferences.getInstance()
                    .writeBoolean(
                            BravePreferenceKeys.BRAVE_TAB_GROUPS_ENABLED_DEFAULT_VALUE, false);
        }
        onInitialLayoutInflationComplete();
    }"""

FINISH_REPLACEMENT = """    @Override
    public void finishNativeInitialization() {
        super.finishNativeInitialization();

        // SANDIUM_FIRST_RUN_BYPASS_V1: avoid silently opting users into telemetry.
        // Respect managed policy; otherwise keep both optional reporting controls off.
        mIsP3aManaged = BraveLocalState.get().isManagedPreference(BravePref.P3A_ENABLED);
        mIsCrashReportingManaged =
                !PrivacyPreferencesManagerImpl.getInstance()
                        .isUsageAndCrashReportingPermittedByPolicy();

        if (!mIsCrashReportingManaged) {
            setMetricsReportingConsent(false, true);
        } else {
            OnboardingPrefManager.getInstance().setP3aCrashReportingMessageShown(true);
        }

        if (!mIsP3aManaged) {
            setP3aConsent(false);
        }

        // This retains Brave's required first-run completion and EULA handoff.
        finalStep();
    }"""

PROMO_PREF_LINE = (
    "        ChromeSharedPreferences.getInstance()\n"
    "                .writeBoolean(OnboardingPrefManager.SHOULD_SHOW_SEARCH_WIDGET_PROMO, true);"
)

def replace_between(source: str, start: str, end: str, replacement: str, label: str) -> str:
    start_at = source.find(start)
    if start_at < 0:
        raise SystemExit(f"FIRST_RUN_PATCH=FAIL missing {label} start anchor")
    end_at = source.find(end, start_at + len(start))
    if end_at < 0:
        raise SystemExit(f"FIRST_RUN_PATCH=FAIL missing {label} end anchor")
    return source[:start_at] + replacement + source[end_at:]


def patch_activity_source(source: str) -> str:
    if MARKER in source:
        if source.count(MARKER) != 3:
            raise SystemExit("FIRST_RUN_PATCH=FAIL partial or unknown activity patch state")
        if PROMO_PREF_LINE in source:
            raise SystemExit("FIRST_RUN_PATCH=FAIL Brave search-widget promo is still queued")
        return source

    source = replace_between(
        source, TRIGGER_START, TRIGGER_END, TRIGGER_REPLACEMENT, "triggerLayoutInflation"
    )
    source = replace_between(
        source, FINISH_START, FINISH_END, FINISH_REPLACEMENT, "finishNativeInitialization"
    )
    if source.count(PROMO_PREF_LINE) != 1:
        raise SystemExit("FIRST_RUN_PATCH=FAIL expected exactly one search-widget promo preference")
    source = source.replace(
        PROMO_PREF_LINE,
        "        // SANDIUM_FIRST_RUN_BYPASS_V1: do not queue Brave's search-widget promotion.",
        1,
    )
    if source.count(MARKER) != 3:
        raise SystemExit("FIRST_RUN_PATCH=FAIL activity marker verification failed")
    if "setMetricsReportingConsent(false, true);" not in source:
        raise SystemExit("FIRST_RUN_PATCH=FAIL crash-reporting opt-out is missing")
    if "setP3aConsent(false);" not in source:
        raise SystemExit("FIRST_RUN_PATCH=FAIL P3A opt-out is missing")
    if "onInitialLayoutInflationComplete();" not in source or "finalStep();" not in source:
        raise SystemExit("FIRST_RUN_PATCH=FAIL first-run completion handoff is missing")
    if PROMO_PREF_LINE in source:
        raise SystemExit("FIRST_RUN_PATCH=FAIL search-widget promotion remains enabled")
    return source


def patch_adapter_source(source: str) -> str:
    if MARKER in source:
        if MARKER not in source or "private static final int[] STEPS = {};" not in source:
            raise SystemExit("FIRST_RUN_PATCH=FAIL partial or unknown adapter patch state")
        return source

    old = (
        "    private static final int[] STEPS = {\n"
        "        R.layout.help_brave_search, R.layout.block_interruptions, R.layout.make_brave_better\n"
        "    };"
    )
    new = (
        "    // SANDIUM_FIRST_RUN_BYPASS_V1: no Brave promotional or first-run cards are exposed.\n"
        "    private static final int[] STEPS = {};"
    )
    if source.count(old) != 1:
        raise SystemExit("FIRST_RUN_PATCH=FAIL expected the pinned three-step adapter definition")
    source = source.replace(old, new, 1)
    if "private static final int[] STEPS = {};" not in source:
        raise SystemExit("FIRST_RUN_PATCH=FAIL empty adapter verification failed")
    return source


def atomic_write(path: Path, content: str) -> None:
    mode = path.stat().st_mode
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.sandium.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as output:
            output.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def verify_pin(core: Path) -> None:
    try:
        sha = subprocess.check_output(
            ["git", "-C", str(core), "rev-parse", "HEAD"], text=True
        ).strip()
        tag = subprocess.check_output(
            ["git", "-C", str(core), "describe", "--tags", "--exact-match"],
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"FIRST_RUN_PIN_GATE=FAIL cannot read Brave Core Git pin: {exc}")
    if sha != EXPECTED_BRAVE_SHA or tag != EXPECTED_BRAVE_TAG:
        raise SystemExit(
            "FIRST_RUN_PIN_GATE=FAIL expected "
            f"{EXPECTED_BRAVE_TAG}@{EXPECTED_BRAVE_SHA}, found {tag}@{sha}"
        )


def apply_to_core(core: Path, check_pin: bool = True) -> None:
    if check_pin:
        verify_pin(core)
    activity = core / ACTIVITY_RELATIVE
    adapter = core / ADAPTER_RELATIVE
    if not activity.is_file() or not adapter.is_file():
        raise SystemExit("FIRST_RUN_PATCH=FAIL pinned Brave onboarding source files are missing")

    activity_updated = patch_activity_source(activity.read_text(encoding="utf-8"))
    adapter_updated = patch_adapter_source(adapter.read_text(encoding="utf-8"))

    if activity_updated != activity.read_text(encoding="utf-8"):
        atomic_write(activity, activity_updated)
    if adapter_updated != adapter.read_text(encoding="utf-8"):
        atomic_write(adapter, adapter_updated)

    print("SANDIUM_FIRST_RUN_BYPASS=PASS")
    print("SANDIUM_FIRST_RUN_PROMOTIONAL_UI=DISABLED")
    print("SANDIUM_FIRST_RUN_PRIVACY_DEFAULTS=P3A_OFF_CRASH_REPORTING_OFF_UNLESS_POLICY_MANAGED")
    print("SANDIUM_FIRST_RUN_EULA_AND_COMPLETION_HANDOFF=PRESERVED")
    print("SANDIUM_SEARCH_WIDGET_PROMO=NOT_QUEUED")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", required=True, type=Path, help="Pinned Brave Core checkout")
    args = parser.parse_args()
    apply_to_core(args.core.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
