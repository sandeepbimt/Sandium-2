"""Pinned Android Autofill switch. Existing mediator owns provider confirmation and prefs."""
from pathlib import Path
BASE='chrome/browser/autofill/android/java/'
PACKAGE=BASE+'src/org/chromium/chrome/browser/autofill/settings/options/'
FRAGMENT=PACKAGE+'AutofillOptionsFragment.java'
BINDER=PACKAGE+'AutofillOptionsViewBinder.java'
XML=BASE+'res/xml/autofill_options_preferences.xml'

def once(s, old, new):
    if new in s: return s
    if s.count(old)!=1: raise ValueError('Autofill UI anchor drift: '+old[:90])
    return s.replace(old,new,1)

def transform(path,s):
    if path==FRAGMENT:
        return once(s,'''    RadioButtonGroupThirdPartyPreference getThirdPartyFillingOption() {
        RadioButtonGroupThirdPartyPreference thirdPartyFillingSwitch =''','''    ChromeSwitchPreference getThirdPartyFillingOption() {
        ChromeSwitchPreference thirdPartyFillingSwitch =''')
    if path==XML:
        return once(s,'''    <org.chromium.chrome.browser.autofill.settings.options.RadioButtonGroupThirdPartyPreference
        android:key="autofill_third_party_filling"
        android:order="1"
        android:selectable="false" />''','''    <!-- SANDIUM_EXTERNAL_AUTOFILL_ONLY: the profile mediator, not Preference persistence, owns this value. -->
    <org.chromium.components.browser_ui.settings.ChromeSwitchPreference
        android:key="autofill_third_party_filling"
        android:order="1"
        android:title="@string/autofill_third_party_filling_opt_in"
        android:defaultValue="false"
        android:persistent="false" />''')
    if path==BINDER:
        start=s.index('        } else if (key == THIRD_PARTY_AUTOFILL_ENABLED) {')
        end=s.index('        } else if (key == THIRD_PARTY_TOGGLE_IS_READ_ONLY) {',start)
        old='''        } else if (key == THIRD_PARTY_AUTOFILL_ENABLED) {
            @RadioButtonGroupThirdPartyPreference.ThirdPartyOption
            int currentOption =
                    model.get(THIRD_PARTY_AUTOFILL_ENABLED)
                            ? RadioButtonGroupThirdPartyPreference.ThirdPartyOption
                                    .USE_OTHER_PROVIDER
                            : RadioButtonGroupThirdPartyPreference.ThirdPartyOption.DEFAULT;
            view.getThirdPartyFillingOption().setSelectedOption(currentOption);
        } else if (key == ON_THIRD_PARTY_TOGGLE_CHANGED) {
            view.getThirdPartyFillingOption()
                    .setOnPreferenceChangeListener(
                            (_, newValue) -> {
                                boolean optedIntoOtherProviders =
                                        (int) newValue
                                                == RadioButtonGroupThirdPartyPreference
                                                        .ThirdPartyOption.USE_OTHER_PROVIDER;
                                model.get(ON_THIRD_PARTY_TOGGLE_CHANGED)
                                        .onResult(optedIntoOtherProviders);
                                return true;
                            });
'''
        new='''        } else if (key == THIRD_PARTY_AUTOFILL_ENABLED) {
            view.getThirdPartyFillingOption().setChecked(model.get(THIRD_PARTY_AUTOFILL_ENABLED));
        } else if (key == ON_THIRD_PARTY_TOGGLE_CHANGED) {
            view.getThirdPartyFillingOption()
                    .setOnPreferenceChangeListener(
                            (_, newValue) -> {
                                model.get(ON_THIRD_PARTY_TOGGLE_CHANGED)
                                        .onResult((boolean) newValue);
                                // The mediator sets the UI, including synchronous cancellation.
                                // Never persist an unconfirmed switch state over that result.
                                return false;
                            });
'''
        if s[start:end] not in (old,new): raise ValueError('Autofill binder drift')
        return s[:start]+new+s[end:]
    raise ValueError(path)

def plan(root):
    return {root/p:transform(p,(root/p).read_text()) for p in (FRAGMENT,BINDER,XML)}
