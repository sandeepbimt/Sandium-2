#!/usr/bin/env python3
"""Explicit test-only composition; never imported/invoked by normal CI."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import patch
import secondary

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('status', ROOT / '.circleci/scripts/apply-sandium-scroll-status-bar.py')
status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status)
geometry_spec = importlib.util.spec_from_file_location('status_geometry', ROOT / '.circleci/scripts/trace-sandium-back-geometry.py')
geometry = importlib.util.module_from_spec(geometry_spec)
geometry_spec.loader.exec_module(geometry)
GATE_OFF = 'private static final boolean SANDIUM_NATIVE_STATUS_CANDIDATE = false;'
GATE_ON = 'private static final boolean SANDIUM_NATIVE_STATUS_CANDIDATE = true;'
SCREEN_OFF = 'private static final boolean SANDIUM_NATIVE_SCREEN_TEST_CANDIDATE = false;'
SCREEN_ON = 'private static final boolean SANDIUM_NATIVE_SCREEN_TEST_CANDIDATE = true;'
NATIVE_BUILD = 'chrome/browser/ui/android/edge_to_edge/internal/BUILD.gn'

def native_build_config(source):
    # Candidate Java references ChromeSemanticColorUtils even with its runtime gate off.
    # Keep the dependency on the implementation target, not unrelated factory consumers.
    marker = 'robolectric_library("junit") {'
    if source.count(marker) != 1:
        raise ValueError('Pinned native-status BUILD target drift')
    implementation, tests = source.split(marker, 1)
    implementation = patch.once(implementation,
            '    "//chrome/browser/ui/android/native_page:java",\n',
            '    "//chrome/browser/ui/android/native_page:java",\n'
            '    "//chrome/browser/ui/android/theme:java",\n')
    return implementation + marker + tests

SECONDARY = {
    'BookmarkActivity.java': 'chrome/android/java/src/org/chromium/chrome/browser/app/bookmarks/BookmarkActivity.java',
    'HistoryActivity.java': 'chrome/android/java/src/org/chromium/chrome/browser/history/HistoryActivity.java',
}
def welcome(source):
    return secondary.transform('WelcomeOnboardingActivity.java', source)

BRAVE = {
    'android/java/org/chromium/chrome/browser/firstrun/WelcomeOnboardingActivity.java': welcome,
    'android/java/org/chromium/chrome/browser/ntp/BraveNewTabPage.java': patch.page,
    'android/java/org/chromium/chrome/browser/ntp/BraveNewTabPageLayout.java': patch.layout,
    'android/java/org/chromium/chrome/browser/settings/BraveSettingsActivity.java': patch.settings_activity,
}

def plan(src, core, enabled=False, native_screens=False):
    """Prepare every transformation before writing any source; fail on anchor drift."""
    if native_screens and not enabled:
        raise ValueError("Native-screen paint experiment requires explicit native-status enable")
    pending = []
    for name, rel in status.FILES.items():
        path = src / rel
        old = path.read_text()
        normalized = old.replace(GATE_ON, GATE_OFF).replace(SCREEN_ON, SCREEN_OFF)
        # Step30 instruments the status method after the ordinary overlay. Its
        # exact known trace must be temporarily reversed before whole-block replay.
        # Reject unknown/duplicate trace payloads; restore diagnostics afterward.
        traced = name == 'EdgeToEdgeControllerImpl.java' and 'SandiumUnderlapReapply' in normalized
        normalized = patch.undo_chromium(name, normalized)
        if traced:
            normalized = geometry.reset(normalized)
        base = status.transform(name, normalized)
        if traced:
            base = geometry.transform(base)
        new = patch.chromium(name, base)
        if name == 'EdgeToEdgeUtils.java':
            if new.count(GATE_OFF) != 1:
                raise ValueError('Native test gate missing or ambiguous')
            if enabled:
                new = new.replace(GATE_OFF, GATE_ON)
        if name in ('EdgeToEdgeBaseLayout.java', 'EdgeToEdgeUtils.java'):
            if new.count(SCREEN_OFF) != 1:
                raise ValueError('Native-screen test gate missing or ambiguous')
            if native_screens:
                new = new.replace(SCREEN_OFF, SCREEN_ON)
        pending.append((path, old, new))
    for name, rel in SECONDARY.items():
        path = src / rel
        old = path.read_text()
        pending.append((path, old, secondary.transform(name, old)))
    build = src / NATIVE_BUILD
    build_old = build.read_text()
    pending.append((build, build_old, native_build_config(build_old)))
    for rel, transform in BRAVE.items():
        path = core / rel
        old = path.read_text()
        if transform is patch.settings_activity and 'private int sandiumSettingsBackground()' not in old:
            raise ValueError('Apply the normal native theme/fade overlays before this candidate')
        pending.append((path, old, transform(old)))
    return pending

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--src', required=True, type=Path)
    parser.add_argument('--core', required=True, type=Path)
    parser.add_argument('--test-only-enable', action='store_true')
    parser.add_argument('--test-only-native-screens', action='store_true',
                        help='Separate unverified unified-root screen experiment; requires --test-only-enable')
    parser.add_argument('--write', action='store_true', help='Otherwise validate and print hashes only')
    args = parser.parse_args()
    pending = plan(args.src, args.core, args.test_only_enable, args.test_only_native_screens)
    for path, old, new in pending:
        if args.write and old != new:
            path.write_text(new)
        print(hashlib.sha256(new.encode()).hexdigest(), path)
    print('TEST_ONLY_NATIVE_STATUS=' + ('ENABLED' if args.test_only_enable else 'DISABLED'))
    print('TEST_ONLY_NATIVE_SCREENS=' + str(args.test_only_native_screens))
    print('SOURCE_WRITE=' + str(args.write))

if __name__ == '__main__':
    main()
