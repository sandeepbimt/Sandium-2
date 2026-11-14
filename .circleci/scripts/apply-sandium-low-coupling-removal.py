#!/usr/bin/env python3
"""Remove residual Android WDP/Origin controls; GN args exclude six native groups."""
from pathlib import Path
import argparse
import re
import tempfile
import shutil


def block_end(text, opening):
    # Only used on known pinned method/control bodies, not arbitrary text.
    depth=0
    for i in range(opening,len(text)):
        if text[i]=='{': depth+=1
        elif text[i]=='}':
            depth-=1
            if depth==0:return i+1
    raise RuntimeError('unbalanced source block')


def remove_block(text, start, replacement=''):
    at=text.find(start)
    if at<0:return text
    if text.count(start)!=1:raise RuntimeError('ambiguous anchor '+start)
    opening=text.index('{',at)
    end=block_end(text,opening)
    return text[:at]+replacement+text[end:]


def search_preferences(text):
    text=text.replace('import org.chromium.components.web_discovery.WebDiscoveryPrefs;\n','')
    text=text.replace('import org.chromium.chrome.browser.BraveConfig;\n','')
    text=re.sub(r'^    private static final String PREF_SEND_WEB_DISCOVERY =.*\n','',text,flags=re.M)
    text=re.sub(r'^    private @Nullable ChromeSwitchPreference mSendWebDiscovery;\n','',text,flags=re.M)
    text=remove_block(text,'        if (BraveConfig.WEB_DISCOVERY_ENABLED) {')
    start='        if (mSendWebDiscovery != null) {'
    if start in text:
        at=text.index(start);end=block_end(text,text.index('{',at))
        tail=text[end:]
        match=re.match(r'\s*else\s*\{',tail)
        if not match:raise RuntimeError('WDP preference else anchor changed')
        end=block_end(text,end+match.end()-1)
        text=text[:at]+text[end:]
    start='                    if (!BraveConfig.WEB_DISCOVERY_ENABLED'
    if start in text:
        at=text.index(start);end=block_end(text,text.index('{',at))
        match=re.match(r'\s*else\s*\{',text[end:])
        if not match:raise RuntimeError('WDP search else anchor changed')
        end=block_end(text,end+match.end()-1)
        text=text[:at]+text[end:]
    # Remove just the final else-if branch while retaining the preceding brace.
    start=' else if (PREF_SEND_WEB_DISCOVERY.equals(key)) {'
    text=remove_block(text,start)
    # Existing Sandium UI overlay may already insert an exclusion by literal key.
    text=text.replace('                    indexData.removeEntryForKey(frag, "send_web_discovery");\n','')
    if re.search(r'WebDiscovery|WEB_DISCOVERY|send_web_discovery',text):
        raise RuntimeError('WDP settings reference remains; inspect pin/overlay composition')
    return text


def welcome(text):
    text=text.replace('import org.chromium.components.web_discovery.WebDiscoveryPrefs;\n','')
    text=re.sub(r'    private static final String WDP_LINK =\n[^;]+;\n','',text)
    text=remove_block(text,'    private void enableWebDiscoverPreference() {')
    text=remove_block(text,'    private boolean isWDPSettingAvailable() {')
    text=text.replace('isWDPSettingAvailable() ? 0 : 1','0')
    text=text.replace('if (position == 2)', 'if (position == 1)')
    text=remove_block(text,'    @Override\n    public void onWebDiscoverPreferenceEnabled() {')
    start='        final ChromeClickableSpan wdpLearnMoreClickableSpan ='
    end='        mOnboardingPager.setUserInputEnabled(false);'
    if start in text:
        a=text.index(start);z=text.index(end,a)
        text=text[:a]+text[z:]
    text=text.replace('new OnboardingStepAdapter(wdpLearnMore, this)',
                      'new OnboardingStepAdapter(this)')
    # Preserve callback interface but remove imports which only the deleted UI used.
    for imp in ('import org.chromium.chrome.browser.BraveConfig;\n',
                'import org.chromium.chrome.browser.customtabs.CustomTabActivity;\n',
                'import org.chromium.ui.text.ChromeClickableSpan;\n',
                'import org.chromium.ui.text.SpanApplier;\n',
                'import org.chromium.ui.text.SpanApplier.SpanInfo;\n'):
        text=text.replace(imp,'')
    if any(x in text for x in ('WebDiscoveryPrefs','BravePref.WEB_DISCOVERY_ENABLED','WDP_LINK','R.string.wdp_text')):
        raise RuntimeError('WDP onboarding behavior remains')
    return text

def onboarding_adapter(text):
    text=text.replace('import android.text.SpannableString;\n','')
    text=text.replace('import android.text.method.LinkMovementMethod;\n','')
    text=text.replace('import android.widget.TextView;\n','')
    text=text.replace('        void onWebDiscoverPreferenceEnabled();\n','')
    text=text.replace('        R.layout.help_brave_search, R.layout.block_interruptions, R.layout.make_brave_better',
                      '        R.layout.block_interruptions, R.layout.make_brave_better')
    text=text.replace('    private static final int HELP_BRAVE_SEARCH_POSITION = 0;\n','')
    text=text.replace('BLOCK_INTERRUPTIONS_POSITION = 1;', 'BLOCK_INTERRUPTIONS_POSITION = 0;')
    text=text.replace('MAKE_BRAVE_BETTER_POSITION = 2;', 'MAKE_BRAVE_BETTER_POSITION = 1;')
    text=text.replace('    private final SpannableString mWdpLearnMore;\n','')
    text=text.replace('    public OnboardingStepAdapter(\n            final SpannableString wdpLearnMore, final OnboardingNavigationListener listener) {\n        mWdpLearnMore = wdpLearnMore;',
                      '    public OnboardingStepAdapter(final OnboardingNavigationListener listener) {')
    text=text.replace('            case HELP_BRAVE_SEARCH_POSITION ->\n                    new HelpBraveSearchViewHolder(view, mWdpLearnMore, mListener);\n','')
    text=remove_block(text,'    private static final class HelpBraveSearchViewHolder extends OnboardingBaseViewHolder {')
    if any(x in text for x in ('help_brave_search','mWdpLearnMore','WebDiscover','HELP_BRAVE_SEARCH_POSITION')):
        raise RuntimeError('WDP adapter reference remains')
    return text



def reporting_welcome(text):
    # Final pass after the Sandium welcome overlay. Keep onboarding completion markers,
    # but remove all reporting choice UI and calls into excluded services.
    for name in ('setMetricsReportingConsent','setP3aConsent','getCrashReportingPreference','getP3aPreference'):
        marker=re.search(r'    private (?:void|boolean) '+name+r'\(',text)
        if marker:text=remove_block(text,text[marker.start():text.index('{',marker.start())+1])
    for name in ('onCrashReportingPreferenceChanged','onP3aPreferenceChanged'):
        text=remove_block(text,'    @Override\n    public void '+name+'(final boolean enabled) {')
    start='        mIsP3aManaged = BraveLocalState.get().isManagedPreference(BravePref.P3A_ENABLED);'
    if start in text:
        a=text.index(start);b=text.index('        org.chromium.chrome.browser.profiles.Profile profile =',a)
        text=text[:a]+text[b:]
    text=remove_block(text,'    @Override\n    public void onRequestPageChange(final int position) {',
        '    @Override\n    public void onRequestPageChange(final int position) {\n        mPageBounceAnimator.animateToPosition(position);\n    }')
    text=re.sub(r'^    private static final String KEY_CRASH_REPORTING_CHECKED =\n[^\n]*\n','',text,flags=re.M)
    text=re.sub(r'^    private static final String KEY_P3A_CHECKED =[^\n]*\n','',text,flags=re.M)
    text=re.sub(r'^    private boolean m(?:IsP3aManaged|IsCrashReportingManaged|CrashReportingChecked|P3aChecked);\n','',text,flags=re.M)
    text=re.sub(r'^        m(?:CrashReportingChecked|P3aChecked) = state.getBoolean[^\n]*\n','',text,flags=re.M)
    for cls in ('BraveLocalState','ChangeMetricsReportingStateCalledFrom','UmaSessionStats','PrivacyPreferencesManagerImpl'):
        text=re.sub(r'^import [^\n]*\.'+cls+r';\n','',text,flags=re.M)
    for token in ('BravePref.P3A_','setMetricsReportingConsent(','setP3aConsent(','mCrashReportingChecked','mP3aChecked'):
        if token in text:raise RuntimeError('reporting onboarding residue: '+token)
    return text


def reporting_adapter(text):
    text=text.replace('import com.google.android.material.checkbox.MaterialCheckBox;\n','')
    text=text.replace(', R.layout.make_brave_better','')
    text=re.sub(r'^    private static final int MAKE_BRAVE_BETTER_POSITION =[^\n]*\n','',text,flags=re.M)
    text=re.sub(r'^    private boolean m(?:CrashReportingChecked|CrashReportingManaged|P3aChecked|P3aManaged);\n','',text,flags=re.M)
    text=re.sub(r'^        void on(?:CrashReporting|P3a)PreferenceChanged[^\n]*\n','',text,flags=re.M)
    a=text.find('            case MAKE_BRAVE_BETTER_POSITION ->')
    if a>=0:
        b=text.index('            default ->',a);text=text[:a]+text[b:]
    text=remove_block(text,'    @Override\n    public void onBindViewHolder(OnboardingBaseViewHolder holder, int position) {',
        '    @Override\n    public void onBindViewHolder(OnboardingBaseViewHolder holder, int position) {}')
    for name in ('setCrashReportingChecked','setCrashReportingManaged','setP3aChecked','setP3aManaged'):
        marker='    public void '+name+'('
        a=text.find(marker)
        if a>=0:text=remove_block(text,text[a:text.index('{',a)+1])
    text=remove_block(text,'    private static final class MakeBraveBetterViewHolder extends OnboardingBaseViewHolder {')
    text=text.replace('view -> listener.onRequestPageChange(MAKE_BRAVE_BETTER_POSITION)', 'view -> listener.onDismiss()')
    for token in ('MakeBraveBetter','MAKE_BRAVE_BETTER','mP3a','mCrashReporting','onP3a','onCrashReporting'):
        if token in text:raise RuntimeError('reporting adapter residue: '+token)
    return text


def adapter_test(text):
    # Rebase assertions for the remaining blocker introduction. Removed features
    # cannot have operational toggle tests; retained step count/dismiss/recycle are tested.
    text=text.replace('import android.text.SpannableString;\n','').replace('import android.widget.TextView;\n','')
    text=text.replace('import android.view.View;\n','').replace('import com.google.android.material.checkbox.MaterialCheckBox;\n','')
    text=text.replace('import static org.junit.Assert.assertFalse;\n','').replace('import static org.junit.Assert.assertTrue;\n','')
    for name in re.findall(r'    @Test\n    public void (test(?:HelpBraveSearch|MakeBraveBetter)\w*)\(',text):
        text=remove_block(text,'    @Test\n    public void '+name+'() {')
    text=text.replace('new OnboardingStepAdapter(mWdpLearnMore, mListener)','new OnboardingStepAdapter(mListener)')
    text=re.sub(r'^    private static final int (?:HELP_BRAVE_SEARCH|MAKE_BRAVE_BETTER) =[^\n]*\n','',text,flags=re.M)
    text=text.replace('BLOCK_INTERRUPTIONS = 1','BLOCK_INTERRUPTIONS = 0').replace('TOTAL_STEPS = 3','TOTAL_STEPS = 1')
    text=re.sub(r'^.*mWdpLearnMore.*\n','',text,flags=re.M)
    text=re.sub(r'^        assertEquals\((?:HELP_BRAVE_SEARCH|MAKE_BRAVE_BETTER), adapter.getItemViewType[^\n]*\n','',text,flags=re.M)
    text=text.replace('getItemViewType(1)','getItemViewType(0)').replace('onCreateViewHolder(mParent, 1)','onCreateViewHolder(mParent, 0)')
    text=text.replace('testBlockInterruptionsNextPage','testBlockInterruptionsDismiss')
    text=text.replace('assertEquals(2, mListener.mRequestedPage);','assertEquals(1, mListener.mDismissCount);')
    for name,args in (('onWebDiscoverPreferenceEnabled',''),('onCrashReportingPreferenceChanged','final boolean enabled'),('onP3aPreferenceChanged','final boolean enabled')):
        text=remove_block(text,'        @Override\n        public void '+name+'('+args+') {')
    text=re.sub(r'^.*m(?:WebDiscoverEnabledCount|CrashReportingChangeCount|P3aChangeCount|LastCrashReportingEnabled|LastP3aEnabled).*\n','',text,flags=re.M)
    return text

ORIGIN_SHELL='''/* Copyright (c) 2026 The Brave Authors. All rights reserved.
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at https://mozilla.org/MPL/2.0/. */
package org.chromium.chrome.browser.settings;

import android.os.Bundle;
import androidx.preference.Preference;
import androidx.preference.PreferenceScreen;
import org.chromium.base.supplier.MonotonicObservableSupplier;
import org.chromium.base.supplier.ObservableSuppliers;
import org.chromium.base.supplier.SettableMonotonicObservableSupplier;

/** Navigation-safe legacy destination. No Origin entitlement or feature toggles. */
public class BraveOriginPreferences extends BravePreferenceFragment {
    public static final String EXTRA_SHOW_RESTART_PROMPT = "show_restart_prompt";
    private final SettableMonotonicObservableSupplier<String> mPageTitle =
            ObservableSuppliers.createMonotonic();
    @Override
    public void onCreatePreferences(Bundle savedInstanceState, String rootKey) {
        mPageTitle.set("Sandium");
        PreferenceScreen screen = getPreferenceManager().createPreferenceScreen(requireContext());
        Preference explanation = new Preference(requireContext());
        explanation.setTitle("Optional components are not included");
        explanation.setSummary("This Sandium build excludes the optional Brave Origin feature groups.");
        explanation.setSelectable(false);
        screen.addPreference(explanation);
        setPreferenceScreen(screen);
    }
    @Override
    public MonotonicObservableSupplier<String> getPageTitle() { return mPageTitle; }
}
'''


def _apply_staged(core):
    settings=core/'android/java/org/chromium/chrome/browser/settings/BraveSearchEnginesPreferences.java'
    settings.write_text(search_preferences(settings.read_text()))
    onboarding=core/'android/java/org/chromium/chrome/browser/firstrun/WelcomeOnboardingActivity.java'
    onboarding.write_text(reporting_welcome(welcome(onboarding.read_text())))
    adapter=core/'browser/first_run/android/java/src/org/chromium/chrome/browser/firstrun/OnboardingStepAdapter.java'
    adapter.write_text(reporting_adapter(onboarding_adapter(adapter.read_text())))
    test=core/'browser/first_run/android/javatests/src/org/chromium/chrome/browser/firstrun/OnboardingStepAdapterTest.java'
    test.write_text(adapter_test(test.read_text()))
    first_run=core/'browser/first_run/android/BUILD.gn';s=first_run.read_text()
    s=re.sub(r'^    "java/res/layout[^"\n]*/help_brave_search[^"\n]*\.xml",\n','',s,flags=re.M)
    s=re.sub(r'^    \"java/res/layout[^\"\n]*/make_brave_better[^\"\n]*\.xml\",\n','',s,flags=re.M)
    first_run.write_text(s)
    config=core/'build/android/config.gni';s=config.read_text()
    s=s.replace('  "//brave/components/web_discovery/browser/android:java_pref_names_srcjar",\n','')
    config.write_text(s)
    xml=core/'android/java/brave-res/xml/brave_search_engines_preferences.xml';s=xml.read_text()
    s=re.sub(r'\s*<org\.chromium\.components\.browser_ui\.settings\.ChromeSwitchPreference\b[^>]*android:key="send_web_discovery"[^>]*/>', '',s)
    if 'send_web_discovery' in s:raise RuntimeError('WDP XML tag changed')
    xml.write_text(s)
    origin=core/'android/java/org/chromium/chrome/browser/settings/BraveOriginPreferences.java'
    origin.write_text(ORIGIN_SHELL)
    gn=core/'android/BUILD.gn';s=gn.read_text()
    s=s.replace('    "java/brave-res/xml/brave_origin_preferences.xml",\n','')
    gn.write_text(s)
    # Remove the unused XML file from packaging, not necessarily the checkout.
    print('SANDIUM_LOW_COUPLING_ANDROID=PASS WDP_controls_removed=true Origin_controls_removed=true')

TOUCHED = ['android/java/org/chromium/chrome/browser/settings/BraveSearchEnginesPreferences.java', 'android/java/org/chromium/chrome/browser/firstrun/WelcomeOnboardingActivity.java', 'android/java/org/chromium/chrome/browser/settings/BraveOriginPreferences.java', 'android/java/brave-res/xml/brave_search_engines_preferences.xml', 'build/android/config.gni', 'android/BUILD.gn', 'browser/first_run/android/BUILD.gn', 'browser/first_run/android/java/src/org/chromium/chrome/browser/firstrun/OnboardingStepAdapter.java', 'browser/first_run/android/javatests/src/org/chromium/chrome/browser/firstrun/OnboardingStepAdapterTest.java']

def apply(core):
    # Validate every transformation before replacing any source in the checkout.
    with tempfile.TemporaryDirectory() as temporary:
        staged=Path(temporary)
        for relative in TOUCHED:
            target=staged/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(core/relative,target)
        _apply_staged(staged)
        for relative in TOUCHED:
            (core/relative).write_text((staged/relative).read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True)
    apply(p.parse_args().core)
