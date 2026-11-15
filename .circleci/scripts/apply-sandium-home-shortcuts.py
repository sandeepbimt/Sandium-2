#!/usr/bin/env python3
"""Pinned native home shortcuts. Preserve Chromium profile custom-link persistence."""
from pathlib import Path
import argparse, subprocess

PACKAGE = 'org/chromium/chrome/browser/suggestions/mostvisited/'
NAME = 'SandiumHomeShortcuts'
def once(t, old, new):
    if new in t: return t
    if t.count(old) != 1: raise ValueError('Home shortcut anchor mismatch: '+old[:100])
    return t.replace(old,new,1)

def shortcut_visibility_listener(t):
    # Two audited complete-line variants: upstream listener (24 spaces) and the
    # exact News-removal replacement (16). Leading newline prevents a 16-space
    # pattern from matching the tail of a 24-space line. Never fuzzy-match.
    variants=[]
    for width in (24,16):
        indent=' ' * width
        old='\n'+indent+'mNtpAdapter.setTopSitesEnabled(mIsTopSitesEnabled);\n'
        new=old+indent+'if (mSandiumShortcuts != null) mSandiumShortcuts.setVisibility(NtpUtil.shouldDisplayTopSites() ? View.VISIBLE : View.GONE);\n'
        variants.append((old,new))
    if sum(t.count(old) for old,new in variants) != 1:
        raise ValueError('Home shortcut listener is not one exact pinned variant')
    old,new=next((old,new) for old,new in variants if old in t)
    return once(t,old,new)

def layout(t):
    t=once(t,'import android.app.Activity;', 'import android.app.Activity;\nimport org.chromium.chrome.browser.suggestions.mostvisited.SandiumHomeShortcuts;')
    t=once(t,'    private boolean mIsTopSitesEnabled;', '''    private @Nullable SandiumHomeShortcuts mSandiumShortcuts;
    private boolean mIsTopSitesEnabled;''')
    t=t.replace('mIsTopSitesEnabled = NtpUtil.shouldDisplayTopSites();','mIsTopSitesEnabled = false; // Sandium owns the native shortcut surface.')
    t=shortcut_visibility_listener(t)
    return once(t,'        mActivity = activity;','''        mActivity = activity;
        if (mSandiumShortcuts == null && !profile.isOffTheRecord()) {
            mSandiumShortcuts = new org.chromium.chrome.browser.suggestions.mostvisited.SandiumHomeShortcuts(
                    getContext(), profile, url -> {
                        org.chromium.chrome.browser.tab.Tab tab = ((BraveActivity) mActivity).getActivityTab();
                        if (tab != null) tab.loadUrl(new org.chromium.content_public.browser.LoadUrlParams(url.getSpec()));
                    });
            android.widget.FrameLayout.LayoutParams shortcutsParams = new android.widget.FrameLayout.LayoutParams(
                    android.view.ViewGroup.LayoutParams.MATCH_PARENT, android.view.ViewGroup.LayoutParams.WRAP_CONTENT,
                    android.view.Gravity.BOTTOM);
            int densityMargin = Math.round(16 * getResources().getDisplayMetrics().density);
            shortcutsParams.leftMargin = densityMargin;
            shortcutsParams.rightMargin = densityMargin;
            shortcutsParams.bottomMargin = Math.round(8 * getResources().getDisplayMetrics().density);
            mSandiumShortcuts.setVisibility(NtpUtil.shouldDisplayTopSites() ? View.VISIBLE : View.GONE);
            addView(mSandiumShortcuts, shortcutsParams);
        }''')

def delegate(t):
    return once(t,'        // Page Zoom\n        final MVCListAdapter.ModelList modelList = new MVCListAdapter.ModelList();','''        // Page Zoom
        final MVCListAdapter.ModelList modelList = new MVCListAdapter.ModelList();
        Tab sandiumHomeTab = mActivityTabProvider.get();
        if (sandiumHomeTab != null && !sandiumHomeTab.isIncognito()
                && ("https".equals(sandiumHomeTab.getUrl().getScheme()) || "http".equals(sandiumHomeTab.getUrl().getScheme()))) {
            modelList.add(new MVCListAdapter.ListItem(AppMenuItemType.STANDARD,
                    AppMenuItemUtils.buildModelForStandardMenuItem(mContext, mAppMenuItemTheme,
                            R.id.sandium_add_home_shortcut, R.string.sandium_add_home_shortcut,
                            R.drawable.ic_baseline_add_24, isMenuIconAtStart())));
        }''')

def activity(t):
    return once(t,'        // Handle items replaced by Brave.','''        if (id == R.id.sandium_add_home_shortcut) {
            boolean saved = org.chromium.chrome.browser.suggestions.mostvisited.SandiumHomeShortcuts.addCurrent(currentTab);
            android.widget.Toast.makeText(this, saved ? R.string.sandium_home_added : R.string.sandium_home_unavailable,
                    android.widget.Toast.LENGTH_SHORT).show();
            return true;
        }
        // Handle items replaced by Brave.''')

def manager(t):
    t=once(t,'          base::FeatureList::IsEnabled(ntp_features::kNtpShortcutsRedesign)',
           '          options.scope == CustomLinksScope::kDesktop &&\n                  base::FeatureList::IsEnabled(ntp_features::kNtpShortcutsRedesign)')
    return once(t,'      current_links_.size() == max_links_) {','      current_links_.size() >= max_links_) {')

def apply(src, repo, verify=False):
    core=src/'brave'
    edits={
        core/'android/java/org/chromium/chrome/browser/ntp/BraveNewTabPageLayout.java':layout,
        core/'android/java/org/chromium/chrome/browser/tabbed_mode/BraveTabbedAppMenuPropertiesDelegate.java':delegate,
        core/'android/java/org/chromium/chrome/browser/app/BraveActivity.java':activity,
        core/'android/java/org/chromium/chrome/browser/suggestions/mostvisited/BraveMostVisitedSites.java':lambda t:once(t,'            if (keep) {','            if (keep && result.size() < 15) { // Keep legacy hidden tile/metrics consumers bounded.'),
        core/'android/brave_java_sources.gni':lambda t:once(t,'  "../../brave/android/java/org/chromium/chrome/browser/ntp/BraveNewTabPageLayout.java",','  "../../brave/android/java/'+PACKAGE+NAME+'.java",\n  "../../brave/android/java/org/chromium/chrome/browser/ntp/BraveNewTabPageLayout.java",'),
        core/'android/java/brave-res/values/brave_ids.xml':lambda t:once(t,'</resources>','    <item name="sandium_add_home_shortcut" type="id"/>\n</resources>'),
        core/'android/BUILD.gn':lambda t:once(t,'    "java/brave-res/values/brave_ids.xml",','    "java/brave-res/values/brave_ids.xml",\n    "java/brave-res/values/sandium_home_strings.xml",'),
        src/'components/ntp_tiles/custom_links_manager_impl.cc':manager,
        src/'chrome/browser/ntp_tiles/chrome_custom_links_manager_factory.cc':lambda t:once(t,'    scope = ntp_tiles::CustomLinksScope::kMobile;','    max_links = 200; // Sandium native expandable shortcut grid; desktop unchanged.\n    scope = ntp_tiles::CustomLinksScope::kMobile;'),
    }
    updates={p:f(p.read_text()) for p,f in edits.items()}
    updates[core/('android/java/'+PACKAGE+NAME+'.java')]=(repo/('android/java/'+PACKAGE+NAME+'.java')).read_text()
    updates[core/'android/java/brave-res/values/sandium_home_strings.xml']=(repo/'android/java/res/values/sandium_home_strings.xml').read_text()
    if verify:
        for p,t in updates.items():
            if not p.exists() or p.read_text()!=t: raise ValueError('Home shortcuts drift: '+str(p))
    else:
        for p,t in updates.items(): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(t)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('src',type=Path);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2]);p.add_argument('--verify-only',action='store_true');a=p.parse_args()
    for path,pin in [(a.src,'d331de35ca8ab1358c7a17e4bd41627d55eaef51'),(a.src/'brave','44a84b1f89d9a35287289d6a3d493e362f5a5123')]:
        if subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()!=pin:
            raise ValueError('Home shortcuts source pin mismatch: '+str(path))
    apply(a.src,a.repo,a.verify_only)
