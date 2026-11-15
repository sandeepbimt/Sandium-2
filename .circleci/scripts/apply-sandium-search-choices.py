#!/usr/bin/env python3
"""Pinned Android UI-only search choices. Does not rewrite saved defaults."""
from pathlib import Path
import argparse
import subprocess
CHROMIUM_PIN = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"

PIN = '44a84b1f89d9a35287289d6a3d493e362f5a5123'
QUICK = 'browser/quick_search_engines/android/java/src/org/chromium/brave/browser/quick_search_engines/utils/QuickSearchEnginesUtil.java'
ADAPTER = 'android/java/org/chromium/chrome/browser/search_engines/settings/BraveBaseSearchEngineAdapter.java'
OLD_QUICK = '''        return ChromeSharedPreferences.getInstance()
                .readBoolean(BravePreferenceKeys.BRAVE_QUICK_SEARCH_ENGINES_FEATURE, true);'''
NEW_QUICK = '''        // SANDIUM_NO_TYPING_ENGINE_STRIP: native omnibox suggestions stay available.
        // Ignore the old strip preference without deleting the user's engine choices.
        return false;'''
OLD_FILTER = '''            TemplateUrl templateUrl = iterator.next();
            if (!templateUrlSet.contains(templateUrl.getShortName())) {'''
NEW_FILTER = '''            TemplateUrl templateUrl = iterator.next();
            // SANDIUM_SEARCH_CHOICES: shared by normal and private selection screens.
            // Brave's pinned prepopulated keyword is :br. Do not remove engines by
            // display name: a user-created engine may legitimately use the same name.
            if (templateUrl.getIsPrepopulated()
                    && (":br".equals(templateUrl.getKeyword())
                            || "search.brave.com".equals(templateUrl.getKeyword()))) {
                iterator.remove();
                continue;
            }
            if (!templateUrlSet.contains(templateUrl.getShortName())) {'''

CHROME = 'chrome/browser/search_engines/android/java/src/org/chromium/chrome/browser/search_engines/settings/SearchEngineAdapter.java'
ACTIVE = 'android/java/org/chromium/chrome/browser/search_engines/settings/BraveSearchEngineAdapter.java'
OLD_LIST = '        // Convert the TemplateUrl index into an item index for the view.'
NEW_LIST = '''        // SANDIUM_SEARCH_CHOICES_V2: filter both provider implementations.
        // Copy because the V2 provider may return immutable lists.
        prepopulatedUrls = new ArrayList<>(prepopulatedUrls);
        recentlyVisitedUrls = new ArrayList<>(recentlyVisitedUrls);
        prepopulatedUrls.removeIf(engine -> engine.getIsPrepopulated()
                && (":br".equals(engine.getKeyword())
                        || "search.brave.com".equals(engine.getKeyword())));
        recentlyVisitedUrls.removeIf(engine -> engine.getIsPrepopulated()
                && (":br".equals(engine.getKeyword())
                        || "search.brave.com".equals(engine.getKeyword())));
        // Convert the TemplateUrl index into an item index for the view.'''
OLD_ACTIVE = '''        if (templateUrl == null) {
            return;
        }
        String keyword = templateUrl.getKeyword();'''
NEW_ACTIVE = '''        // SANDIUM_SEARCH_DEFAULT_MIGRATION: only replace a removed Brave choice.
        TemplateUrlService sandiumService = templateUrlServiceArg != null
                ? templateUrlServiceArg : TemplateUrlServiceFactory.getForProfile(profile);
        if (templateUrl != null && sandiumService != null && sandiumService.isLoaded()
                && !sandiumService.isDefaultSearchManaged()
                && templateUrl.getIsPrepopulated()
                && (":br".equals(templateUrl.getKeyword())
                        || "search.brave.com".equals(templateUrl.getKeyword()))) {
            for (TemplateUrl candidate : sandiumService.getTemplateUrls()) {
                if (candidate.getIsPrepopulated()
                        && candidate.getPrepopulatedId() == 1
                        && (":g".equals(candidate.getKeyword())
                                || "google.com".equals(candidate.getKeyword()))) {
                    templateUrl = candidate;
                    setDSEPrefs(candidate.getShortName(), profile);
                    break;
                }
            }
        }
        if (templateUrl == null) {
            return;
        }
        String keyword = templateUrl.getKeyword();'''
OLD_START = '''        try {
            super.start();'''
NEW_START = '''        try {
            // SANDIUM_SEARCH_CHOICES_START: migrate before the list snapshots the DSE.
            TemplateUrlService sandiumService = TemplateUrlServiceFactory.getForProfile(mProfile);
            if (sandiumService != null && sandiumService.isLoaded()) {
                updateActiveDSE(mProfile, sandiumService);
            }
            super.start();'''
OLD_LOADED = '''        super.onTemplateUrlServiceLoaded();'''
NEW_LOADED = '''        // SANDIUM_SEARCH_CHOICES_LOADED: normal and private adapters both use this.
        updateActiveDSE(mProfile, null);
        super.onTemplateUrlServiceLoaded();'''

def replace(s, old, new):
    if new in s:
        if s.count(new) != 1: raise ValueError('Duplicate search overlay')
        return s
    if s.count(old) != 1: raise ValueError('Pinned search source anchor mismatch')
    return s.replace(old, new, 1)

def outputs(core):
    return [(core/QUICK, replace((core/QUICK).read_text(), OLD_QUICK, NEW_QUICK)),
            (core/ADAPTER, replace((core/ADAPTER).read_text(), OLD_FILTER, NEW_FILTER)),
            (core/ACTIVE, replace(replace(replace((core/ACTIVE).read_text(), OLD_ACTIVE, NEW_ACTIVE), OLD_START, NEW_START), OLD_LOADED, NEW_LOADED)),
            (core.parent/CHROME, replace((core.parent/CHROME).read_text(), OLD_LIST, NEW_LIST))]

def apply(core, verify=False):
    if subprocess.check_output(['git','-C',str(core),'rev-parse','HEAD'], text=True).strip() != PIN:
        raise ValueError('Unexpected Brave pin')
    if subprocess.check_output(['git','-C',str(core.parent),'rev-parse','HEAD'], text=True).strip() != CHROMIUM_PIN:
        raise ValueError('Unexpected Chromium pin')
    result = outputs(core)
    for p, value in result:
        if verify:
            if p.read_text() != value: raise ValueError('Search overlay missing: '+str(p))
        else: p.write_text(value)

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--verify-only',action='store_true')
    a=p.parse_args();apply(a.core,a.verify_only)
