#!/usr/bin/env python3
"""Pinned Dark Pages Java/pref/UI layer. Not wired until native consumers pass review."""
from pathlib import Path
import argparse
import subprocess
import xml.etree.ElementTree as ET

CHROMIUM_PIN='d331de35ca8ab1358c7a17e4bd41627d55eaef51'
BRAVE_PIN='44a84b1f89d9a35287289d6a3d493e362f5a5123'
MODULE='chrome/browser/ui/android/night_mode/'
THEME=MODULE+'java/src/org/chromium/chrome/browser/night_mode/WebContentsThemeClient.java'
PROFILE='browser/brave_profile_prefs.cc'
SHIELDS='android/java/org/chromium/chrome/browser/shields/BraveUnifiedPanelHandler.java'
APPEARANCE='android/java/org/chromium/chrome/browser/settings/AppearancePreferences.java'
LAYOUT='android/java/brave-res/layout/brave_shields_tab_content.xml'
WELCOME='android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java'
A='{http://schemas.android.com/apk/res/android}'
ET.register_namespace('android',A[1:-1])
ET.register_namespace('app','http://schemas.android.com/apk/res-auto')
ET.register_namespace('tools','http://schemas.android.com/tools')

def once(text, old, new):
    if new in text: return text
    if text.count(old)!=1: raise ValueError('Dark Pages pinned anchor drift: '+old[:100])
    return text.replace(old,new,1)

def theme(text):
    text=once(text,'import org.chromium.content_public.browser.WebContents;','import org.chromium.content_public.browser.WebContents;\nimport org.chromium.url.GURL;')
    text=text.replace('@JniType("GURL") org.chromium.url.GURL documentUrl','@JniType("GURL") GURL documentUrl')
    if 'SANDIUM_DARK_PAGES_POLICY_V1' in text: return text
    anchor='public class WebContentsThemeClient {'
    return once(text,anchor,anchor+'''
    // SANDIUM_DARK_PAGES_POLICY_V1: native consumers use the same resolved policy.
    @CalledByNative
    public static int sandiumDarkPageFlags(
            @JniType("content::WebContents*") WebContents webContents,
            @JniType("GURL") GURL documentUrl) {
        return SandiumDarkPages.flags(webContents, documentUrl);
    }
''')

def module(text):
    sources=['org/chromium/chrome/browser/night_mode/SandiumDarkPages.java',
             'org/chromium/chrome/browser/sandium/dark/DarkPagePolicy.java']
    anchor='android_library("java") {\n  sources = [\n'
    entries=''.join('    "java/src/'+p+'",\n' for p in sources)
    text=once(text,anchor,anchor+entries)
    # First deps belongs to the production java target, not only tests.
    anchor='  deps = [\n    ":java_resources",\n'
    return once(text,anchor,anchor+'    "//components/prefs/android:java",\n    "//components/user_prefs/android:java",\n')

def profile(text):
    if 'registry->RegisterStringPref("sandium.dark_pages.policy_v1", "");' in text: return text
    anchor='void RegisterProfilePrefs(user_prefs::PrefRegistrySyncable* registry) {\n'
    return once(text,anchor,anchor+'''  // Sandium origin-scoped dark policies. Not syncable; private policies stay in memory.
  registry->RegisterStringPref("sandium.dark_pages.policy_v1", "");
''')

def shields(text):
    old = """        // Independent from the Shields ad-block master switch.
        View darkPages = popupView.findViewById(R.id.sandium_dark_pages_button);
        if (darkPages != null) {
            darkPages.setOnClickListener(v -> {
                if (mContext != null && mCurrentTab != null) {
                    org.chromium.chrome.browser.sandium.dark.SandiumDarkPagesUi.showSite(
                            mContext, mCurrentTab);
                }
            });
        }
"""
    entry = """        // Independent from the Shields ad-block master switch.
        org.chromium.chrome.browser.sandium.dark.SandiumDarkPagesUi.bindSiteToggle(
                mContext, mCurrentTab, popupView, () -> hide());
"""
    if entry in text: return text
    if old in text: return once(text, old, entry)
    anchor='        setupAdvancedOptionsListeners();\n'
    return once(text,anchor,anchor+entry)

def appearance(text):
    anchor='        SettingsUtils.addPreferencesFromResource(this, R.xml.brave_appearance_preferences);\n'
    text=once(text,'''                    .setChecked(ChromeFeatureList.isEnabled(
                            BraveFeatureList.FORCE_WEB_CONTENTS_DARK_MODE));''', '''                    .setChecked(org.chromium.chrome.browser.night_mode.SandiumDarkPages.global(
                            getProfile(), org.chromium.chrome.browser.sandium.dark.DarkPagePolicy.Control.DARK_PAGE));''')
    text=once(text,'''            BraveFeatureUtil.enableFeature(
                    BraveFeatureList.ENABLE_FORCE_DARK, (boolean) newValue, true);
            shouldRelaunch = true;''', '''            if (!org.chromium.chrome.browser.night_mode.SandiumDarkPages.trySetGlobal(
                    getProfile(), org.chromium.chrome.browser.sandium.dark.DarkPagePolicy.Control.DARK_PAGE,
                    (boolean) newValue)) {
                android.widget.Toast.makeText(requireContext(), R.string.sandium_dark_pages_failed,
                        android.widget.Toast.LENGTH_SHORT).show();
                return false;
            }''')
    return once(text,anchor,anchor+'''
        androidx.preference.Preference darkPages = new androidx.preference.Preference(requireContext());
        darkPages.setKey("sandium_dark_pages");
        darkPages.setTitle(R.string.sandium_dark_pages_global);
        darkPages.setSummary(R.string.sandium_dark_pages_reload_notice);
        darkPages.setOnPreferenceClickListener(preference -> {
            org.chromium.chrome.browser.sandium.dark.SandiumDarkPagesUi.showGlobal(
                    requireContext(), getProfile());
            return true;
        });
        getPreferenceScreen().addPreference(darkPages);
''')

def welcome(text):
    if 'SANDIUM_DARK_PAGES_WELCOME_V1' in text:
        text = text.replace('mSandiumDarkPageSwitch = addSwitchRow(card, "☾", "Dark pages",',
                            'mSandiumDarkPageSwitch = addRestartSwitchRow(card, "☾", "Dark pages",')
        marker = '// The registered policy defaults are already enabled; do not overwrite saved choices.'
        if '// Setup restart applies startup-only transition choices.' not in text:
            text = once(text, marker, marker + "\n        // Setup restart applies startup-only transition choices.\n        mRequiresRestart = true;")
        return text
    text=once(text,'''        // Brave feature overrides are read during native startup; relaunch after
        // completing first run so the selected Night Mode is actually active.
        BraveFeatureUtil.enableFeature(BraveFeatureList.ENABLE_FORCE_DARK, true, true);
        mRequiresRestart = true;''', '''        // SANDIUM_DARK_PAGES_WELCOME_V1: profile policy applies to webpage preferences.
        // The registered policy defaults are already enabled; do not overwrite saved choices.
        // Setup restart applies startup-only transition choices.
        mRequiresRestart = true;''')
    text=once(text, '        applyInitialPreferences();\n', '''        applyInitialPreferences();
        if (mSandiumDarkPageSwitch != null
                && org.chromium.chrome.browser.night_mode.SandiumDarkPages.usable(mProfile)) {
            mSandiumRestoringDarkPageSwitch = true;
            mSandiumDarkPageSwitch.setChecked(
                    org.chromium.chrome.browser.night_mode.SandiumDarkPages.global(mProfile,
                            org.chromium.chrome.browser.sandium.dark.DarkPagePolicy.Control.DARK_PAGE));
            mSandiumRestoringDarkPageSwitch = false;
        }
''')
    text=once(text,'    private Profile mProfile;', '    private Profile mProfile;\n    private Switch mSandiumDarkPageSwitch;\n    private boolean mSandiumRestoringDarkPageSwitch;')
    return once(text,'''        addRestartSwitchRow(card, "☾", "Night Mode",
                "Force dark mode for web content",
                true, checked -> {
                    BraveFeatureUtil.enableFeature(BraveFeatureList.ENABLE_FORCE_DARK, checked, true);
                    mRequiresRestart = true;
                });''', '''        mSandiumDarkPageSwitch = addRestartSwitchRow(card, "☾", "Dark pages",
                "Use native dark rendering for websites",
                true, checked -> {
                    if (mSandiumRestoringDarkPageSwitch) return;
                    if (!org.chromium.chrome.browser.night_mode.SandiumDarkPages.trySetGlobal(
                            mProfile, org.chromium.chrome.browser.sandium.dark.DarkPagePolicy.Control.DARK_PAGE,
                            checked)) {
                        mSandiumRestoringDarkPageSwitch = true;
                        mSandiumDarkPageSwitch.setChecked(!checked);
                        mSandiumRestoringDarkPageSwitch = false;
                        android.widget.Toast.makeText(mActivity, R.string.sandium_dark_pages_failed,
                                android.widget.Toast.LENGTH_SHORT).show();
                    }
                });''')

def layout(text):
    if '@+id/sandium_dark_pages_button' in text:
        root=ET.fromstring(text)
        node=next(n for n in root.iter() if n.get(A+'id')=='@+id/sandium_dark_pages_button')
        if node.tag == 'androidx.appcompat.widget.SwitchCompat': return text
        node.tag='androidx.appcompat.widget.SwitchCompat'
        ET.indent(root,space='    ')
        return text[:text.index('<LinearLayout')]+ET.tostring(root,encoding='unicode')+'\n'
    if 'SANDIUM_GROUPED_POPUP_V1' not in text: raise ValueError('Grouped popup must apply first')
    root=ET.fromstring(text)
    node=ET.Element('androidx.appcompat.widget.SwitchCompat')
    for key,value in {'id':'@+id/sandium_dark_pages_button','layout_width':'match_parent',
            'layout_height':'wrap_content','minHeight':'48dp','gravity':'center_vertical',
            'paddingHorizontal':'16dp','paddingVertical':'12dp','layout_marginTop':'10dp',
            'background':'@drawable/advanced_options_bg','text':'@string/sandium_dark_pages_title',
            'textColor':'?attr/colorOnSurface','textSize':'16sp','clickable':'true','focusable':'true'}.items():
        node.set(A+key,value)
    # Outside protection-dependent advanced content: site appearance remains reachable with Shields off.
    root.insert(2,node)
    ET.indent(root,space='    ')
    return text[:text.index('<LinearLayout')]+ET.tostring(root,encoding='unicode')+'\n'

def transformations(src,repo):
    core=src/'brave'; feature=repo/'.circleci/features/dark-pages'
    outputs={src/THEME:theme((src/THEME).read_text()),
             src/(MODULE+'BUILD.gn'):module((src/(MODULE+'BUILD.gn')).read_text()),
             core/PROFILE:profile((core/PROFILE).read_text()),
             core/SHIELDS:shields((core/SHIELDS).read_text()),
             core/APPEARANCE:appearance((core/APPEARANCE).read_text()),
             core/LAYOUT:layout((core/LAYOUT).read_text()),
             core/WELCOME:welcome((core/WELCOME).read_text())}
    for relative in ('org/chromium/chrome/browser/night_mode/SandiumDarkPages.java',
                     'org/chromium/chrome/browser/sandium/dark/DarkPagePolicy.java'):
        outputs[src/(MODULE+'java/src/'+relative)]=(feature/'java'/relative).read_text()
    relative='org/chromium/chrome/browser/sandium/dark/SandiumDarkPagesUi.java'
    outputs[core/'android/java'/relative]=(feature/'java'/relative).read_text()
    path=core/'android/brave_java_sources.gni'
    entry='  "../../brave/android/java/'+relative+'",\n'
    current=path.read_text()
    outputs[path]=current if entry in current else once(current,'brave_java_sources = [\n','brave_java_sources = [\n'+entry)
    path=core/'android/BUILD.gn';anchor='    "java/brave-res/values/brave_ids.xml",\n'
    entry='    "java/brave-res/values/sandium_dark_pages_strings.xml",\n'
    current=path.read_text()
    outputs[path]=current if entry in current else once(current,anchor,anchor+entry)
    outputs[core/'android/java/brave-res/values/sandium_dark_pages_strings.xml']=(
            feature/'res/values/sandium_dark_pages_strings.xml').read_text()
    return outputs

def apply(src,repo,verify=False):
    for path,pin in ((src,CHROMIUM_PIN),(src/'brave',BRAVE_PIN)):
        if subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()!=pin:
            raise ValueError('Dark Pages source pin mismatch')
    for path,text in transformations(src,repo).items():
        if verify:
            if not path.exists() or path.read_text()!=text: raise ValueError('Dark Pages drift: '+str(path))
        else:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('src',type=Path);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2]);p.add_argument('--verify-only',action='store_true')
    args=p.parse_args();apply(args.src,args.repo,args.verify_only)
