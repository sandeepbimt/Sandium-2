"""Four explicit blur choices; only unobscured outgoing-blur reveal gets a longer fade."""
from pathlib import Path
STARTUP='chrome/android/java/src/org/chromium/chrome/browser/base/SplitCompatApplication.java'
SETTINGS='brave/android/java/org/chromium/chrome/browser/settings/AppearancePreferences.java'
XML='brave/android/java/brave-res/xml/brave_appearance_preferences.xml'
CC='content/browser/navigation_transitions/blur_transition_animation_manager.cc'
INPUTS={STARTUP,SETTINGS,XML,CC}
KEY='sandium_page_transition_blur_choice'
HELPER='''    private static String getSandiumBlurLevel() {
        android.content.SharedPreferences prefs = ContextUtils.getAppSharedPreferences();
        String choice = prefs.getString("sandium_page_transition_blur_choice", "");
        if ("off".equals(choice) || "low".equals(choice)
                || "medium".equals(choice) || "high".equals(choice)) return choice;
        if (prefs.contains("sandium_page_transition_blur_enabled")) {
            return prefs.getBoolean("sandium_page_transition_blur_enabled", true) ? "low" : "off";
        }
        String legacy = prefs.getString("sandium_page_transition_blur_level", "on");
        return "default".equals(legacy) || "off".equals(legacy) ? "off" : "low";
    }
'''
def once(s,a,b):
    if s.count(a)!=1:raise ValueError('Four-level blur anchor drift: '+a[:70])
    return s.replace(a,b,1)
def method(s,signature,replacement):
    start=s.index(signature);a=s.index('{',start);depth=1;b=a+1
    while depth:
        depth+=(s[b]=='{')-(s[b]=='}');b+=1
    return s[:start]+replacement+s[b:]
def startup(s):
    a=s.index('            final String blurKey = "sandium_page_transition_blur_enabled";')
    b=s.index('            final CommandLine handoffCommandLine',a)
    s=s[:a]+'''            final String blurChoice = getSandiumBlurLevel();
            final boolean blurOn = !"off".equals(blurChoice);
'''+s[b:]
    s=once(s,'!handoffBlurFeature.equals(name) && !dimFeature.equals(name)',
        '!handoffBlurFeature.equals(name) && !dimFeature.equals(name)\n                            && !"SandiumNavigationTransitionFade".equals(name)')
    s=once(s,'                handoffCommandLine.appendSwitchWithValue(switchName, cleaned.toString());','''                if (enable && ("medium".equals(blurChoice) || "high".equals(blurChoice))) {
                    if (cleaned.length() > 0) cleaned.append(',');
                    cleaned.append("SandiumNavigationTransitionFade:duration-ms/")
                            .append("high".equals(blurChoice) ? "200" : "175");
                }
                handoffCommandLine.appendSwitchWithValue(switchName, cleaned.toString());''')
    return once(s,'    private static String getSandiumFeatureName(',HELPER+'\n    private static String getSandiumFeatureName(')
def settings(s):
    s=once(s,'PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL = "sandium_page_transition_blur_enabled";',
        'PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL = "sandium_page_transition_blur_choice";')
    s=once(s,'''        ChromeSwitchPreference pageTransitionBlur =
                (ChromeSwitchPreference) findPreference(PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL);''','''        ListPreference pageTransitionBlur =
                (ListPreference) findPreference(PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL);''')
    s=once(s,'            pageTransitionBlur.setChecked(isSandiumNativeBlurEnabled());','''            pageTransitionBlur.setEntries(new CharSequence[] {getString(R.string.sandium_welcome_off),
                    getString(R.string.sandium_welcome_blur_low), getString(R.string.sandium_welcome_blur_medium),
                    getString(R.string.sandium_welcome_blur_high)});
            pageTransitionBlur.setEntryValues(new CharSequence[] {"off", "low", "medium", "high"});
            pageTransitionBlur.setValue(getSandiumBlurLevel());''')
    s=method(s,'private static boolean isSandiumNativeBlurEnabled()', '''private static boolean isSandiumNativeBlurEnabled() {
        return !"off".equals(getSandiumBlurLevel());
    }\n\n'''+HELPER)
    s=once(s,'''            if (!(newValue instanceof Boolean)) return false;
            boolean saved = ContextUtils.getAppSharedPreferences().edit()
                    .putBoolean("sandium_page_transition_blur_enabled", (Boolean) newValue).commit();''','''            if (!(newValue instanceof String)) return false;
            String level = (String) newValue;
            if (!"off".equals(level) && !"low".equals(level)
                    && !"medium".equals(level) && !"high".equals(level)) return false;
            boolean saved = ContextUtils.getAppSharedPreferences().edit()
                    .putString("sandium_page_transition_blur_choice", level)
                    .putBoolean("sandium_page_transition_blur_enabled", !"off".equals(level)).commit();''')
    s=once(s,'if (darken != null) darken.setEnabled((Boolean) newValue);','if (darken != null) darken.setEnabled(!"off".equals(level));')
    return s
def xml(s):
    a=s.index('    <org.chromium.components.browser_ui.settings.ChromeSwitchPreference\n        android:key="sandium_page_transition_blur_enabled"')
    b=s.index('/>',a)+2
    node=s[a:b].replace('org.chromium.components.browser_ui.settings.ChromeSwitchPreference','androidx.preference.ListPreference').replace('sandium_page_transition_blur_enabled','sandium_page_transition_blur_choice').replace('android:defaultValue="true"','android:defaultValue="low"')
    return s[:a]+node+s[b:]
NATIVE='''// The optional longer reveal never changes fallback fade or native input ownership.
BASE_FEATURE(kSandiumNavigationTransitionFade, base::FEATURE_DISABLED_BY_DEFAULT);
const base::FeatureParam<int> kSandiumRevealDurationMs{
    &kSandiumNavigationTransitionFade, "duration-ms", 150};
static base::TimeDelta GetSandiumRevealDuration(bool has_blur, float fallback_opacity) {
  if (!has_blur || fallback_opacity > 0.0f ||
      !base::FeatureList::IsEnabled(kSandiumNavigationTransitionFade)) {
    return GetBlurFadeOutDuration();
  }
  return base::Milliseconds(std::clamp(kSandiumRevealDurationMs.Get(), 150, 200));
}

'''
def native(s):
    s=once(s,'#include "base/feature_list.h"','#include "base/feature_list.h"\n#include "base/metrics/field_trial_params.h"')
    s=once(s,'static float GetBlurSigma() {',NATIVE+'static float GetBlurSigma() {')
    return once(s,'''    case AnimationState::kFadeOut: {
      progress = std::clamp(elapsed / GetBlurFadeOutDuration(), 0.0, 1.0);''','''    case AnimationState::kFadeOut: {
      progress = std::clamp(elapsed / GetSandiumRevealDuration(
          !!blur_layer_, initial_fallback_opacity_), 0.0, 1.0);''')
def plan(root):
    root=Path(root)
    return {root/p:f((root/p).read_text()) for p,f in [(STARTUP,startup),(SETTINGS,settings),(XML,xml),(CC,native)]}
