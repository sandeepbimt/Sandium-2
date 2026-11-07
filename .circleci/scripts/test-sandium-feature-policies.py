#!/usr/bin/env python3
"""Offline regression checks for Sandium's 13 disabled Brave features."""
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[2]
PREPARE = ROOT / ".circleci/scripts/prepare-brave-source.sh"
OVERLAY = ROOT / ".circleci/scripts/apply-sandium-full-overlays.py"

EXPECTED_GN_ARGS = (
    "enable_brave_rewards:false",
    "enable_brave_news:false",
    "enable_brave_vpn_v1:false",
    "enable_brave_vpn_v2:false",
    "enable_brave_wallet:false",
    "enable_ai_chat:false",
    "enable_brave_talk:false",
    "enable_brave_wayback_machine:false",
    "enable_speedreader:false",
    "enable_tor:false",
    "enable_web_discovery_native:false",
    "enable_web_discovery:false",
)

PLAYLIST_UTILS_FIXTURE = """bool IsDisabledByPolicy(PrefService* prefs) {
  return prefs->IsManagedPreference(kPlaylistEnabledPref) &&
         !prefs->GetBoolean(kPlaylistEnabledPref);
}

}  // namespace

bool IsPlaylistAllowed(PrefService* prefs) {
  DCHECK(prefs);
  return base::FeatureList::IsEnabled(features::kPlaylist) &&
         !IsDisabledByPolicy(prefs);
}
"""


def main() -> None:
    prepare = PREPARE.read_text(encoding="utf-8")
    overlay_source = OVERLAY.read_text(encoding="utf-8")
    full_mode = prepare.split('if [ "$MODE" = "full" ]; then', 1)[1].split(
        'elif [ "$MODE" = "fast" ]; then', 1
    )[0]

    for argument in EXPECTED_GN_ARGS:
        needle = "--gn " + argument
        assert full_mode.count(needle) == 1, f"missing/duplicate Full Mode GN arg: {needle}"
    assert "enable_playlist:false" not in prepare, (
        "Pinned Android buildflags explicitly reject enable_playlist=false"
    )

    assert "SANDIUM_P3A_DEFAULT" in overlay_source
    assert "SANDIUM_P3A_RUNTIME" in overlay_source
    assert "local_state_->SetBoolean(kP3AEnabled, false);" in overlay_source
    assert "SANDIUM_STATS_REPORTING_DEFAULT" in overlay_source
    assert "SANDIUM_STATS_REPORTING_RUNTIME" in overlay_source
    assert "pref_service_->SetBoolean(kStatsReportingEnabled, false);" in overlay_source
    assert "SANDIUM_WEB_DISCOVERY_NATIVE" in overlay_source
    assert "SANDIUM_WEB_DISCOVERY" in overlay_source
    assert "SANDIUM_ANDROID_NEWS_TEST_DEP_GUARD" in overlay_source

    module = runpy.run_path(str(OVERLAY))
    transform = module["transform_playlist_utils"]
    transformed = transform(PLAYLIST_UTILS_FIXTURE)
    assert transformed == module["PLAYLIST_UTILS_NEW"]
    assert transform(transformed) == transformed, "Playlist overlay must be idempotent"
    try:
        transform("unexpected upstream Playlist implementation")
    except RuntimeError:
        pass
    else:
        raise AssertionError("Playlist overlay must fail closed on source drift")

    factory_transform = module["transform_playlist_factory"]
    factory_fixture = (
        '#include "brave/components/playlist/content/browser/type_converter.h"\\n'
        '    registry->RegisterBooleanPref(kPlaylistEnabledPref, true);\\n'
        + module["PLAYLIST_FACTORY_OLD"]
    )
    factory_updated = factory_transform(factory_fixture)
    assert 'registry->RegisterBooleanPref(kPlaylistEnabledPref, false);' in factory_updated
    assert 'profile->GetPrefs()->SetBoolean(kPlaylistEnabledPref, false);' in factory_updated
    assert 'if (!IsPlaylistAllowed(profile->GetPrefs()))' in factory_updated
    assert '#include "brave/components/playlist/core/browser/utils.h"' in factory_updated
    assert factory_transform(factory_updated) == factory_updated, (
        "Playlist service factory overlay must be idempotent"
    )

    # The only runtime C++ policy override in this change is Playlist's
    # allow-check; Shields and the native ad-blocker source are not touched.
    assert "brave_shields" not in module["PLAYLIST_UTILS_NEW"]
    assert "cosmetic_filters" not in module["PLAYLIST_UTILS_NEW"]
    assert "uBlock" not in module["PLAYLIST_UTILS_NEW"]

    print("SANDIUM_FEATURE_POLICY_TEST=PASS disabled=13 mode=full shields=untouched")


if __name__ == "__main__":
    main()
