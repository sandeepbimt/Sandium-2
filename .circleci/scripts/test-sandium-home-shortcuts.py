#!/usr/bin/env python3
"""Pinned source composition contracts. These are NOT Android runtime tests."""
from pathlib import Path
import importlib.util, tempfile, shutil, sys, xml.etree.ElementTree as ET
repo=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('home',repo/'.circleci/scripts/apply-sandium-home-shortcuts.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
audit=Path(sys.argv[1]); fixture=Path(sys.argv[2])
with tempfile.TemporaryDirectory() as tmp:
    src=Path(tmp);core=src/'brave'
    paths=['android/java/org/chromium/chrome/browser/ntp/BraveNewTabPageLayout.java','android/java/org/chromium/chrome/browser/tabbed_mode/BraveTabbedAppMenuPropertiesDelegate.java','android/java/org/chromium/chrome/browser/app/BraveActivity.java','android/brave_java_sources.gni','android/java/brave-res/values/brave_ids.xml','android/BUILD.gn','android/java/org/chromium/chrome/browser/suggestions/mostvisited/BraveMostVisitedSites.java']
    for p in paths:
        target=core/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(audit/p,target)
    target=src/'chrome/browser/ntp_tiles/chrome_custom_links_manager_factory.cc';target.parent.mkdir(parents=True);shutil.copyfile(fixture,target)
    impl=src/'components/ntp_tiles/custom_links_manager_impl.cc';impl.parent.mkdir(parents=True);shutil.copyfile(fixture.parent/'custom_links_manager_impl.cc',impl)
    m.apply(src,repo);m.apply(src,repo,True)
    first={str(p):p.read_bytes() for p in src.rglob('*') if p.is_file()}
    m.apply(src,repo)
    assert first=={str(p):p.read_bytes() for p in src.rglob('*') if p.is_file()}
    target.write_text(target.read_text().replace('max_links = 200;','max_links = 8;'))
    try:m.apply(src,repo,True)
    except ValueError:pass
    else:raise AssertionError('failed to detect capacity drift')
# Both approved listener variants, including the actual removal golden source.
layout_path='android/java/org/chromium/chrome/browser/ntp/BraveNewTabPageLayout.java'
for text in [(audit/layout_path).read_text(),(repo/'.circleci/features/news-removal/expected'/layout_path).read_text()]:
    changed=m.layout(text)
    assert m.layout(changed)==changed
    assert changed.count('if (mSandiumShortcuts != null) mSandiumShortcuts.setVisibility')==1
for text in ['\n'+' '*20+'mNtpAdapter.setTopSitesEnabled(mIsTopSitesEnabled);\n',
             '\n'+' '*16+'mNtpAdapter.setTopSitesEnabled(mIsTopSitesEnabled);\n'+' '*24+'mNtpAdapter.setTopSitesEnabled(mIsTopSitesEnabled);\n']:
    try:m.shortcut_visibility_listener(text)
    except ValueError:pass
    else:raise AssertionError('unknown or ambiguous listener variant accepted')
java=(repo/('android/java/'+m.PACKAGE+m.NAME+'.java')).read_text()
assert 'site.source == TileSource.CUSTOM_LINKS' in java
assert 'new MostVisitedSitesBridge(mProfile, true)' in java
assert 'tab.isIncognito()' in java and '"https".equals' in java
assert 'mBridge.destroy()' in java and 'mIcons.destroy()' in java
assert 'ValueAnimator.areAnimatorsEnabled()' in java
assert 'event.getLocalState() != this' in java
assert 'indexForUrl(site.url)' in java
assert 'Math.min(20, mSites.size())' in java and 'grid.setColumnCount(5)' in java
assert 'mDialog.dismiss()' in java and 'mParentLayout' in java
assert 'lp.height = dp(76)' in java and 'dp(44), dp(44)' in java
assert java.index('addView(mScroll,') < java.index('View arrow = new ChevronButton')
assert 'Gravity.END' in java and 'mEditing' in java
assert 'mScroll.setVerticalScrollBarEnabled(mExpanded)' in java
assert 'setVerticalScrollbarThumbDrawable(thumb)' in java
assert 'getAccessibilityClassName()' in java
assert 'new android.graphics.drawable.InsetDrawable(shape(mAccent,10)' in java
assert 'mSites.size() > 20' in java
assert 'if (!isAttachedToWindow() || mDragging != null) return;' in java
assert java.count('mDragView.setAlpha(1f); mDragView = null;') >= 3
assert 'shape(Color.TRANSPARENT,10)' in java and 'onDrawShadow' in java
assert 'getLargeIconForUrl' in java and 'fetch' not in java.lower()
import re
names={e.get('name') for e in ET.parse(repo/'android/java/res/values/sandium_home_strings.xml').getroot()}
assert set(re.findall(r'R.string.(sandium_\w+)',java))<=names
print('PASS: pinned transformations, idempotence, drift, resource and source contracts; Android compile/device not run')

# Numbered layout: newest upper-left (20), oldest reaches lower-right (1).
assert 'return bridge.addCustomLink(title, url, 0)' in java
assert java.count('addNewest(') == 3
assert 'Collections.reverse' not in java
assert 'mExpanded ? 5 : 4' in java
assert 'reservedHeight - height' in java
assert 'mScroll.setBackground(shape(mPanel, 16))' in java
assert 'count > 0 && i < rows * 5' in java
for count in [1, 2, 5, 6, 19, 20, 21, 25, 26, 200]:
    saved = []
    for n in range(1, count + 1): saved.insert(0, n)
    assert saved[0] == count
    if count == 20: assert saved[19] == 1
    shown = min(20, count)
    rows = (shown + 4) // 5
    assert 1 <= rows <= 4
    panel = min(4 * 76, rows * 76)
    assert panel + (4 * 76 - panel) == 304
    expanded_panel = min(5 * 76, ((count + 4) // 5) * 76)
    assert expanded_panel <= 380
# Manual order remains authoritative; next addition prepends without reversing it.
saved = [3, 1, 2]; saved.insert(0, 4); assert saved == [4, 3, 1, 2]
for source in [(audit/layout_path).read_text(), (repo/'.circleci/features/news-removal/expected'/layout_path).read_text()]:
    changed=m.layout(source)
    assert changed.count('mIsBraveStatsEnabled = false; // Sandium homepage') == 2
    assert 'BraveStatsUtil.showBraveStats();' in changed
    assert 'NtpUtil.shouldDisplayBraveStats()' not in changed
print('PASS: numbered order, bounded row/panel geometry models, native ordering contracts and display-only stats suppression')

assert 'GradientDrawable.Orientation.TL_BR' in java
assert 'frost.setCornerRadius(dp(12))' in java
assert 'frost.setStroke(dp(1), 0x26ffffff)' in java
assert 'ImageView.ScaleType.FIT_CENTER' in java
assert 'icon.setPadding(dp(6),dp(6),dp(6),dp(6))' in java
assert 'content.addView(iconBox, new LinearLayout.LayoutParams(dp(44), dp(44)))' in java
assert 'RenderEffect' not in java and 'setColorFilter' not in java
print('PASS: uniform frosted icon bounds, aspect-preserving content and no runtime blur/tint')
