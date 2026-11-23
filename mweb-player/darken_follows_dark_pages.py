"""RawS: keep native blur independent; decide its tint from destination Dark Pages."""
import argparse
from pathlib import Path

from glue import once
import seal

BASE = '046433ccc90f73eb4409538c38dc9f846ba9e8aa'
MAN = 'fcfd5f06a0eaee536d810b33c1903736e0f0d9f29c131288aa62a0452149f24b'
PROOF = 'e5135f90d0662d13380d4d9757a9e1964221ba59cc11d1685af05d6ad0cffcc9'
ANDROID = 'chrome/android/java/src/org/chromium/chrome/browser/'
APP = ANDROID + 'appearance/settings/AppearanceSettingsFragment.java'
WELCOME = ANDROID + 'firstrun/RawSSetupFirstRunFragment.java'
STARTUP = ANDROID + 'base/RawSNavigationAppearance.java'
PREF_XML = 'chrome/android/java/res/xml/appearance_preferences.xml'
WELCOME_XML = 'chrome/android/java/res/values/raws_welcome_palette.xml'
SETTINGS_XML = 'chrome/android/java/res/values/raws_main_settings_strings.xml'
CCB = 'chrome/browser/chrome_content_browser_client.cc'
CCB_H = 'chrome/browser/chrome_content_browser_client.h'
CLIENT = 'content/public/browser/content_browser_client.cc'
CLIENT_H = 'content/public/browser/content_browser_client.h'
BLUR = 'content/browser/navigation_transitions/blur_transition_animation_manager.cc'
OWNERS = {
    APP: 'c7b571d52e0774093d00a60fd71941adc2d58b340dc8d600044f751b44a050e3',
    WELCOME: 'b82c4f0d69614c451d59756abc0e1ad9a11ed05ecb631e8a689b735cbb80744a',
    STARTUP: '1544f66d64d5212268131e6c595b9dc12a8f227f8feed9dccfe5d39fc0971091',
    PREF_XML: '0e5be5adff8b10f4ada1d45eb7a9fa73dabc6cc829143e168352c99a94aa2d9c',
    WELCOME_XML: 'fcc2b1fd925859c79b8df6d3cc028cd999b751b23b8541d25a1ccb98624de628',
    SETTINGS_XML: 'b5b73398be62f95eee0b907c651d1b7c6777237d19495c3b0be8183ea8363d8c',
    CCB: '9f7bca8a004ed80471b2b80d51fc6738aaeff442f74add8ec4d458189fb0ca4d',
    CCB_H: 'aacd31c8315b00260ffc4594f225e75854889db4e4c81cdb9adf2ebf51f6ffad',
    CLIENT: '9d612e328877199e0e68e765a84c66f6e098774991b5fb8f91fc3f62e4e4efb1',
    CLIENT_H: '16df8b59c07eee17a785e92dcd9eb6ba01150ac9ef8c884baa16795239625162',
    BLUR: '26fc78ed6c63008781d50245dce3838429e325d262de3371c9fd480b41fcaef2',
}


def span(text, start, end, new):
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError('ambiguous transform span')
    a = text.index(start)
    b = text.index(end, a)
    return text[:a] + new + text[b:]


def transform(path, original):
    s = original.decode()
    if path == APP:
        s = span(s, '        ChromeSwitchPreference darken =\n',
                 '        darkPages.setOnPreferenceChangeListener(',
                 '        if (darkPages == null || blur == null) return;\n')
        s = span(s, '        darken.setChecked(', '\n    private void updateRawSDarkPages()', '''        blur.setOnPreferenceChangeListener(
                (preference, value) -> RawSNavigationAppearance.setBlurLevel((String) value));
    }
''')
    elif path == WELCOME:
        for old in (
            '    private boolean mStagedDarken;\n',
            '    private boolean mInitialDarken;\n',
            '        mInitialDarken = RawSNavigationAppearance.isDarkenEnabled();\n',
            '        mStagedDarken = mInitialDarken;\n',
            '            mStagedDarken = !"off".equals(mStagedBlur)\n'
            '                    && state.getBoolean("darken", mStagedDarken);\n',
            '        state.putBoolean("darken", mStagedDarken);\n',
            '                    boolean blurActive = !"off".equals(mStagedBlur);\n'
            '                    if (!blurActive) {\n'
            '                        mStagedDarken = false;\n'
            '                        darken.setChecked(false);\n'
            '                    }\n'
            '                    darken.setEnabled(blurActive);\n',
        ):
            s = once(s, old, '')
        s = span(s, '        updateBlurLabel(blur);\n        divider(settings);',
                 '        Button more = rowButton(', '''        updateBlurLabel(blur);
        blur.setOnClickListener(v -> showBlurPicker(blur));
        divider(settings);
''')
        s = once(s, '''        return !mInitialBlur.equals(mStagedBlur)
                || (!"off".equals(mStagedBlur) && mInitialDarken != mStagedDarken);''',
                 '''        return !mInitialBlur.equals(mStagedBlur);''')
        s = once(s, 'showBlurPicker(Button blur, Switch darken)', 'showBlurPicker(Button blur)')
        s = once(s, '''        if ((!mInitialBlur.equals(mStagedBlur) || mInitialDarken != mStagedDarken)
                && !RawSNavigationAppearance.setChoices(mStagedBlur, mStagedDarken)) {''',
                 '''        if (restartNeeded()
                && !RawSNavigationAppearance.commitBlurLevel(mStagedBlur)) {''')
    elif path == STARTUP:
        s = once(s, '    private static final String DARKEN_PREF = "sandium_page_transition_darken";\n', '')
        s = span(s, '    public static boolean isDarkenEnabled()', '    static void applyBeforeNativeFeatureList()', '''    public static boolean setBlurLevel(String level) {
        if (!validLevel(level)) return false;
        prefs().edit().putString(BLUR_PREF, level).apply();
        return true;
    }

    /** Persist staged Welcome blur before a possible process restart. */
    public static boolean commitBlurLevel(String level) {
        if (!validLevel(level)) return false;
        return prefs().edit().putString(BLUR_PREF, level).commit();
    }

''')
        s = span(s, '        // Leave native blur timing', '    private static String appendFeature(', '''        // Leave native blur, opacity, and timing at Chromium defaults.
        commandLine.appendSwitchWithValue(ENABLE, appendFeature(enable, FEATURE));
    }

''')
    elif path == PREF_XML:
        s = span(s, '    <org.chromium.components.browser_ui.settings.ChromeSwitchPreference\n'
                 '        android:key="raws_parity_darken_transition"',
                 '    <org.chromium.components.browser_ui.settings.ChromeBasePreference\n'
                 '        android:key="raws_saved_color_rules"', '')
    elif path == WELCOME_XML:
        s = once(s, '    <string name="raws_setup_darken">Darken transition</string>\n'
                 '    <string name="raws_setup_darken_summary">Dim the outgoing page</string>\n', '')
    elif path == SETTINGS_XML:
        s = once(s, '    <string name="raws_settings_darken_transition">Darken transition</string>\n', '')
    elif path == CLIENT_H:
        anchor = '  virtual int GetRawSPageTextPolicyForNavigation(WebContents* web_contents);'
        s = once(s, anchor, anchor + '''

  // Whether the incoming document's browser-owned Dark Pages setting requests
  // tint for the existing Android blur transition. No effect on blur admission.
  virtual bool ShouldDarkenRawSNavigation(WebContents* web_contents,
                                          const GURL& destination);
''')
    elif path == CLIENT:
        anchor = 'int ContentBrowserClient::GetRawSPageTextPolicyForNavigation('
        s = once(s, anchor, '''bool ContentBrowserClient::ShouldDarkenRawSNavigation(WebContents*,
                                                     const GURL&) {
  return false;
}

''' + anchor)
    elif path == CCB_H:
        anchor = '  int GetRawSPageTextPolicyForNavigation('
        s = once(s, anchor, '''  bool ShouldDarkenRawSNavigation(content::WebContents* web_contents,
                                  const GURL& destination) override;
''' + anchor)
    elif path == CCB:
        anchor = 'int ChromeContentBrowserClient::GetRawSPageTextPolicyForNavigation('
        s = once(s, anchor, '''bool ChromeContentBrowserClient::ShouldDarkenRawSNavigation(
    content::WebContents* web_contents,
    const GURL& destination) {
#if BUILDFLAG(IS_ANDROID)
  if (!web_contents || !destination.is_valid() ||
      !destination.SchemeIsHTTPOrHTTPS()) {
    return false;
  }
  auto* profile = Profile::FromBrowserContext(web_contents->GetBrowserContext());
  auto* settings = profile ? HostContentSettingsMapFactory::GetForProfile(profile)
                           : nullptr;
  // Same effective setting as RawSDarkPages.isDarkForSite. Use the actual
  // tab profile (including OTR) and the final URL, not the outgoing tab URL.
  return settings &&
         settings->GetContentSetting(destination, destination,
                                     ContentSettingsType::AUTO_DARK_WEB_CONTENT) ==
             CONTENT_SETTING_ALLOW;
#else
  return false;
#endif
}

''' + anchor)
    elif path == BLUR:
        s = once(s, '  if (features::kAndroidNavigationAnimationDarken.Get()) {',
                 '''  if (GetContentClient()->browser()->ShouldDarkenRawSNavigation(
          web_contents(), navigation_handle->GetURL())) {''')
    else:
        raise ValueError(path)
    return s.encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if Path.cwd() != Path(__file__).resolve().parents[1]:
        raise ValueError('run in checkout root')
    read = lambda name: seal.git('show', BASE + ':' + name)
    out = seal.plan(read, owners=OWNERS, edit=transform, man=MAN, proof=PROOF)
    if args.write:
        if seal.git('rev-parse', 'HEAD').decode().strip() != BASE:
            raise ValueError('wrong checkout')
        for name, data in out.items():
            p = Path(name)
            if p.is_symlink() or (p.exists() and p.read_bytes() !=
                    (data if name.startswith(seal.IMAGE) else read(name))):
                raise ValueError('dirty or unsafe overlay path: ' + name)
    for name, data in sorted(out.items()):
        if args.write:
            Path(name).write_bytes(data)
        print(seal.digest(data), name)


if __name__ == '__main__':
    main()
