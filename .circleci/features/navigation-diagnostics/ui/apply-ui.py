#!/usr/bin/env python3
"""Diagnostics settings UI composition. Recorder/wiring is owned separately."""
from pathlib import Path
import argparse

PACKAGE = 'org/chromium/chrome/browser/sandium/diagnostics/'
NAMES = ('SandiumDiagnosticsPreferences.java', 'SandiumDiagnosticsCapture.java')
TAB = 'chrome/android/java/src/org/chromium/chrome/browser/tab/TabWebContentsObserver.java'
MAIN = 'android/java/org/chromium/chrome/browser/settings/BraveMainPreferencesBase.java'
ANCHOR = '        SettingsUtils.addPreferencesFromResource(this, R.xml.brave_main_preferences);\n'
BLOCK = '''
        // SANDIUM_DIAGNOSTICS_SETTINGS_V1: opt-in, local-only event recording.
        androidx.preference.Preference diagnostics = new androidx.preference.Preference(requireContext());
        diagnostics.setKey("sandium_navigation_diagnostics");
        diagnostics.setTitle("Navigation diagnostics");
        diagnostics.setSummary("Record, stop, and export local troubleshooting events");
        diagnostics.setIcon(R.drawable.ic_bar_chart);
        diagnostics.setOrder(999);
        diagnostics.setFragment(
                org.chromium.chrome.browser.sandium.diagnostics.SandiumDiagnosticsPreferences.class.getName());
        getPreferenceScreen().addPreference(diagnostics);
'''


def main_settings(source):
    source = source.replace(BLOCK, '')
    if source.count(ANCHOR) != 1:
        raise ValueError('Pinned main settings anchor drift')
    return source.replace(ANCHOR, ANCHOR + BLOCK, 1)


def java_source(source, name):
    entry = '  "../../brave/android/java/' + PACKAGE + name + '",\n'
    if entry in source:
        return source
    anchor = 'brave_java_sources = [\n'
    if source.count(anchor) != 1:
        raise ValueError('Pinned Java source list anchor drift')
    # Insert before the closing list, preserving other owners' contiguous header anchors.
    end = source.index(']', source.index(anchor) + len(anchor))
    return source[:end] + entry + source[end:]


def java_sources(source):
    for name in NAMES:
        source = java_source(source, name)
    return source

def tab_bootstrap(source):
    # Bootstrap before construction: super(tab) may initialize web-content observers.
    anchor = '    public static TabWebContentsObserver from(Tab tab) {\n'
    call = '        org.chromium.chrome.browser.sandium.diagnostics.SandiumDiagnosticsCapture.install();\n'
    source = source.replace(call, '')
    if source.count(anchor) != 1:
        raise ValueError('Pinned Tab observer factory drift')
    return source.replace(anchor, anchor + call, 1)

def outputs(src, feature):
    core = src / 'brave'
    result = {
        src / TAB: tab_bootstrap((src / TAB).read_text()),
        core / MAIN: main_settings((core / MAIN).read_text()),
        core / 'android/brave_java_sources.gni': java_sources(
            (core / 'android/brave_java_sources.gni').read_text()),
    }

    for name in NAMES:
        result[core / 'android/java' / PACKAGE / name] = (feature / name).read_text()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('src', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    for path, content in outputs(args.src, Path(__file__).resolve().parent).items():
        if args.verify_only:
            if not path.exists() or path.read_text() != content:
                raise SystemExit('Diagnostics UI composition drift: ' + str(path))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
