#!/usr/bin/env python3
"""Compose text-settings UI/persistence for the pinned tree. Not a CI pipeline activation.

Renderer integration must be reviewed and wired separately before this transform is exposed.
No page-load callback, late injection or page mutation is introduced here.
"""
from pathlib import Path
import argparse
import subprocess
import xml.etree.ElementTree as ET

A = '{http://schemas.android.com/apk/res/android}'
ET.register_namespace('android', A[1:-1])
PACKAGE = 'org/chromium/chrome/browser/sandium/text/'
MODULE = 'chrome/browser/ui/android/night_mode/'
PREF = 'sandium.page_text.policy_v1'

def once(s, old, new):
    if new in s: return s
    if s.count(old) != 1: raise ValueError('Page text anchor drift: ' + old[:100])
    return s.replace(old, new, 1)

def profile(s):
    anchor = 'void RegisterProfilePrefs(user_prefs::PrefRegistrySyncable* registry) {\n'
    return once(s, anchor, anchor + '  registry->RegisterStringPref("' + PREF + '", "");\n')

def appearance(s):
    anchor = '        SettingsUtils.addPreferencesFromResource(this, R.xml.brave_appearance_preferences);\n'
    return once(s, anchor, anchor + '''
        // SANDIUM_PAGE_TEXT_SETTINGS_V1: profile defaults, not app UI font scaling.
        androidx.preference.Preference pageText = new androidx.preference.Preference(requireContext());
        pageText.setKey("sandium_page_text");
        pageText.setTitle("Webpage text");
        pageText.setSummary("Text size and optional article typography");
        pageText.setOnPreferenceClickListener(preference -> {
            org.chromium.chrome.browser.sandium.text.SandiumPageTextUi.showGlobal(
                    requireContext(), getProfile());
            return true;
        });
        getPreferenceScreen().addPreference(pageText);
''')

def theme(s):
    anchor = 'public class WebContentsThemeClient {'
    return once(s, anchor, anchor + '''
    // SANDIUM_PAGE_TEXT_COMMIT_V1: called with the final browser-validated URL.
    @CalledByNative
    public static int sandiumPageTextPolicy(
            @JniType("content::WebContents*") WebContents webContents,
            @JniType("GURL") GURL documentUrl) {
        return org.chromium.chrome.browser.sandium.text.SandiumPageText.packed(
                webContents, documentUrl);
    }
''')

def outputs(src, repo):
    core = src/'brave'
    feature = repo/'.circleci/features/page-text/java'/PACKAGE
    paths = {
        'browser/brave_profile_prefs.cc': profile,
        'android/java/org/chromium/chrome/browser/settings/AppearancePreferences.java': appearance,
    }
    out = {core/p: fn((core/p).read_text()) for p,fn in paths.items()}
    for name in ('PageTextPolicy.java', 'PageTextStylesheet.java', 'SandiumPageText.java'):
        out[src/MODULE/'java/src'/PACKAGE/name] = (feature/name).read_text()
    out[core/'android/java'/PACKAGE/'SandiumPageTextUi.java'] = (feature/'SandiumPageTextUi.java').read_text()
    path = src/MODULE/'BUILD.gn'
    text = path.read_text()
    for name in ('PageTextPolicy.java', 'PageTextStylesheet.java', 'SandiumPageText.java'):
        anchor = 'android_library("java") {\n  sources = [\n'
        entry = '    "java/src/'+PACKAGE+name+'",\n'
        if entry not in text: text = once(text, anchor, anchor + entry)
    # The prerequisite Dark Pages transform already declares prefs/user_prefs dependencies.
    for dependency in ('//components/prefs/android:java', '//components/user_prefs/android:java'):
        if dependency not in text: raise ValueError('Missing existing night mode dependency: '+dependency)
    out[path] = text
    path = src/MODULE/'java/src/org/chromium/chrome/browser/night_mode/WebContentsThemeClient.java'
    out[path] = theme(path.read_text())
    path = core/'android/brave_java_sources.gni'
    anchor = 'brave_java_sources = [\n'
    out[path] = once(path.read_text(), anchor,
            anchor+'  "../../brave/android/java/'+PACKAGE+'SandiumPageTextUi.java",\n')
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('src',type=Path)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[4])
    p.add_argument('--verify-only',action='store_true');args=p.parse_args()
    for path,pin in ((args.src,'d331de35ca8ab1358c7a17e4bd41627d55eaef51'),
            (args.src/'brave','44a84b1f89d9a35287289d6a3d493e362f5a5123')):
        actual=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
        if actual != pin: raise SystemExit('Page text source pin mismatch: '+str(path))
    for path,text in outputs(args.src,args.repo).items():
        if args.verify_only:
            if path.read_text()!=text: raise SystemExit('Page text drift: '+str(path))
        else: path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
if __name__=='__main__':main()
