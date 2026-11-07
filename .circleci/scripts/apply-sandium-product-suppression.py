#!/usr/bin/env python3
"""Pin-guarded runtime policy gates for Sandium's disabled Brave products."""
from pathlib import Path
import argparse
import subprocess
import sys

BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"

POLICIES = (
    (
        "android/java/org/chromium/chrome/browser/vpn/BraveVpnPolicy.java",
        """    public static boolean isDisabledByPolicy(@Nullable Profile profile) {
        if (profile == null) {
            return false;
        }
        PrefService prefService = UserPrefs.get(profile);
        return prefService.isManagedPreference(BravePref.MANAGED_BRAVE_VPN_DISABLED)
                && prefService.getBoolean(BravePref.MANAGED_BRAVE_VPN_DISABLED);
    }""",
        """    public static boolean isDisabledByPolicy(@Nullable Profile profile) {
        // Sandium Full Mode ships without Brave VPN; hide all policy-gated entry points.
        return true;
    }""",
        "SANDIUM_VPN_POLICY",
    ),
    (
        "android/java/org/chromium/chrome/browser/brave_news/BraveNewsPolicy.java",
        """    public static boolean isDisabledByPolicy(@Nullable Profile profile) {
        if (profile == null) {
            return false;
        }
        PrefService prefService = UserPrefs.get(profile);
        return prefService.isManagedPreference(BravePref.BRAVE_NEWS_DISABLED_BY_POLICY)
                && prefService.getBoolean(BravePref.BRAVE_NEWS_DISABLED_BY_POLICY);
    }""",
        """    public static boolean isDisabledByPolicy(@Nullable Profile profile) {
        // Sandium Full Mode ships without Brave News; hide all policy-gated entry points.
        return true;
    }""",
        "SANDIUM_NEWS_POLICY",
    ),
    (
        "android/java/org/chromium/chrome/browser/BraveRewardsPolicy.java",
        """    public static boolean isDisabledByPolicy(@Nullable Profile profile) {
        if (sDisabledByPolicyForTesting != null) {
            return sDisabledByPolicyForTesting;
        }
        if (profile == null) {
            return false;
        }
        PrefService prefService = UserPrefs.get(profile);
        return prefService.isManagedPreference(BravePref.DISABLED_BY_POLICY)
                && prefService.getBoolean(BravePref.DISABLED_BY_POLICY);
    }""",
        """    public static boolean isDisabledByPolicy(@Nullable Profile profile) {
        if (sDisabledByPolicyForTesting != null) {
            return sDisabledByPolicyForTesting;
        }
        // Sandium Full Mode ships without Brave Rewards; retain test override support.
        return true;
    }""",
        "SANDIUM_REWARDS_POLICY",
    ),
)

def apply_policy_file(path: Path, old_method: str, new_method: str, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"{label}=FAIL missing pinned source: {path}")
    source = path.read_text(encoding="utf-8")
    if source.count(new_method) == 1 and old_method not in source:
        print(f"{label}=ALREADY_APPLIED")
        return
    count = source.count(old_method)
    if count != 1:
        raise RuntimeError(f"{label}=FAIL expected exactly one upstream policy method; found {count}")
    path.write_text(source.replace(old_method, new_method, 1), encoding="utf-8")
    verified = path.read_text(encoding="utf-8")
    if verified.count(new_method) != 1 or old_method in verified:
        raise RuntimeError(f"{label}=FAIL post-write verification failed")
    print(f"{label}=PASS")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", required=True, type=Path)
    args = parser.parse_args()
    core = args.core.resolve()
    actual_sha = subprocess.check_output(
        ["git", "-C", str(core), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual_sha != BRAVE_SHA:
        raise RuntimeError(
            f"SANDIUM_PRODUCT_POLICY_PIN=FAIL expected={BRAVE_SHA} actual={actual_sha}"
        )
    for relative_path, old_method, new_method, label in POLICIES:
        apply_policy_file(core / relative_path, old_method, new_method, label)
    print("SANDIUM_PRODUCT_SUPPRESSION=PASS VPN=disabled News=disabled Rewards=disabled")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SANDIUM_PRODUCT_SUPPRESSION=FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
