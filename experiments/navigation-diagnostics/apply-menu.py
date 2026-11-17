#!/usr/bin/env python3
"""Profile-owned bridge for optional appmenu numeric evidence sink."""
from pathlib import Path
PATH='brave/android/java/org/chromium/chrome/browser/tabbed_mode/BraveTabbedAppMenuPropertiesDelegate.java'
OLD='        CustomizeBraveMenu.applyCustomization(mContext.getResources(), modelList);'
REC='org.chromium.chrome.browser.sandium.diagnostics.SandiumNavigationDiagnostics'
NEW=OLD+'''
        // SANDIUM_MENU_DIAGNOSTICS_PROFILE_V1: never infer a private profile.
        final var sandiumDiagnosticTab = mActivityTabProvider.get();
        if (sandiumDiagnosticTab != null && sandiumDiagnosticTab.getProfile() != null
                && !sandiumDiagnosticTab.getProfile().isOffTheRecord()) {
            org.chromium.chrome.browser.ui.appmenu.SandiumMenuMetadata.diagnostics(
                    modelList, (event, values) -> {
                        if (event < 16 || event > 18 || !'''+REC+'''.isRecording()
                                || mActivityTabProvider.get() != sandiumDiagnosticTab
                                || sandiumDiagnosticTab.isDestroyed()
                                || sandiumDiagnosticTab.getProfile() == null
                                || sandiumDiagnosticTab.getProfile().isOffTheRecord()) return;
                        '''+REC+'''.record(
                                '''+REC+'''.Event.values()[event], 0,
                                sandiumDiagnosticTab.getProfile().isOffTheRecord(), values);
                    });
        }
'''
def transform(s):
 if NEW in s:return s
 if s.count(OLD)!=1:raise ValueError('Menu diagnostic profile anchor drift')
 return s.replace(OLD,NEW,1)
