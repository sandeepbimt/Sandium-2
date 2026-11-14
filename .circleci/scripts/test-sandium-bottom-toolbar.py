#!/usr/bin/env python3
"""Source-contract checks only. These are not Android compilation/runtime tests."""
import argparse
import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET
import sys

spec = importlib.util.spec_from_file_location('toolbar', Path(__file__).with_name('apply-sandium-bottom-toolbar.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
p = argparse.ArgumentParser()
p.add_argument('--upstream-fixtures',type=Path,help='Exact pinned Chromium source files, flat filenames')
p.add_argument('--src',type=Path,help='Post-apply Chromium source tree; no pristine fixtures required')
p.add_argument('--core',type=Path,required=True,help='Pinned Brave source checkout; read-only')
a = p.parse_args()

if a.src:
    src=a.src
    phone=(src/m.PHONE).read_text()
    pref=(src/m.PREF).read_text()
    brave=(a.core/m.BRAVE).read_text()
    command=(a.core/'android/java/org/chromium/base/BraveCommandLineInitUtil.java').read_text()
    layout=(src/m.BASE/'java/res/layout/toolbar_phone.xml').read_text()
    menu=(src/m.BASE/'java/res/layout/menu_button.xml').read_text()
    build=(src/m.BASE/'BUILD.gn').read_text()
    for transform,text in [(m.phone,phone),(m.preference,pref),(m.brave,brave),
                           (m.commandline,command),(m.layout,layout),(m.menu,menu),(m.build,build)]:
        assert transform(text)==text, transform.__name__+' not fully applied'
    assert 'SANDIUM_NATIVE_BOTTOM_TOOLBAR_V1' in phone
    assert 'setClickCallback(' in phone and 'tabController.forward()' in phone
    assert 'onNavigationStateChanged()' in phone
    assert 'mSandiumObservedTab.canGoForward()' in phone
    assert 'removeObserver(mSandiumNavigationObserver)' in phone
    assert 'setHasSpaceToShow(true)' in phone
    assert 'findViewById(R.id.sandium_shields_row)' in phone
    assert 'ClipboardManager' not in phone and 'getPrimaryClip' not in phone
    assert 'if (LocalStatePrefs.get() == null) return ToolbarPositionAndSource.BOTTOM_SETTINGS;' in pref
    assert pref.index('setToolbarPositionAndSource(ToolbarPositionAndSource.BOTTOM_SETTINGS);') < pref.index('putBoolean("bottom-native-v1", true)')
    assert 'isNonMultiDisplayContextOnTablet' in pref
    assert 'getMenuOrKeyboardActionController()' in brave
    assert 'R.id.new_incognito_tab_menu_id : R.id.new_tab_menu_id' in brave
    assert 'mBraveShieldsButton.setOnClickListener(this)' in brave
    assert 'showShieldsMenu();' in brave
    assert 'sandiumDisabledFeatures.append("AndroidBottomBar")' in command
    assert 'getSwitchValue("disable-features", "")' in command
    root=ET.fromstring(layout)
    android='{http://schemas.android.com/apk/res/android}'
    ids=[node.get(android+'id') for node in root.iter()]
    for name in ('sandium_shields_row','sandium_new_tab','tab_switcher_button','location_bar'):
        assert ids.count('@+id/'+name)==1, 'Expected one '+name
    assert layout.count('@layout/menu_button')==1
    assert layout.count('@layout/brave_toolbar')==1
    assert layout.index('@layout/brave_toolbar') < layout.index('@+id/sandium_new_tab') < layout.index('@+id/tab_switcher_button') < layout.index('@layout/menu_button')
    assert 'org.chromium.chrome.browser.omnibox.LocationBarPhone' in layout
    assert '<EditText' not in layout
    assert '@drawable/sandium_toolbar_menu' in menu
    for resource,expected in m.resources().items():
        actual=(src/m.BASE/resource).read_text()
        assert actual==expected, 'Resource changed: '+resource
        ET.fromstring(actual)
        assert build.count('"'+resource+'"')==1, 'GN resource entry missing/duplicate: '+resource
    print('PASS: applied native-toolbar source/resource contracts. NOT compiled/device-tested.')
    sys.exit(0)

if not a.upstream_fixtures:
    p.error('choose --src for post-apply checks or --upstream-fixtures for pristine transform tests')

cases = [(m.phone,a.upstream_fixtures/'ToolbarPhone.java'),
         (m.preference,a.upstream_fixtures/'AddressBarPreference.java'),
         (m.menu,a.upstream_fixtures/'menu_button.xml'),
         (m.build,a.upstream_fixtures/'BUILD.gn'),(m.brave,a.core/m.BRAVE),
         (m.commandline,a.core/'android/java/org/chromium/base/BraveCommandLineInitUtil.java')]
for transform,path in cases:
    source=path.read_text()
    result=transform(source)
    assert result != source, transform.__name__+' fixture was already transformed'
    assert transform(result)==result, transform.__name__+' is not idempotent'

# Reproduce the exact Brave layout include before overlaying. Shield assets never change.
layout=(a.upstream_fixtures/'toolbar_phone.xml').read_text()
layout=layout.replace('        <ViewStub\n            android:id="@+id/optional_button_stub"', '''        <include layout="@layout/brave_toolbar"
            android:layout_height="@dimen/brave_toolbar_button_height"
            android:layout_width="match_parent"
            android:layout_marginTop="@dimen/location_bar_vertical_margin" />

        <ViewStub
            android:id="@+id/optional_button_stub"''',1)
out=m.layout(layout)
assert m.layout(out)==out
ET.fromstring(out)
assert out.count('@+id/sandium_new_tab')==1
assert out.count('@+id/tab_switcher_button')==1
assert out.count('@layout/brave_toolbar')==1
assert out.index('@layout/brave_toolbar') < out.index('@+id/sandium_new_tab') < out.index('@+id/tab_switcher_button') < out.index('@layout/menu_button')
assert 'org.chromium.chrome.browser.omnibox.LocationBarPhone' in out
assert '<EditText' not in out
for resource,text in m.resources().items(): ET.fromstring(text)
phone=m.phone((a.upstream_fixtures/'ToolbarPhone.java').read_text())
assert 'tabController.forward()' in phone
assert 'mSandiumObservedTab.canGoForward()' in phone
assert 'R.drawable.sandium_toolbar_forward' in phone
assert 'ClipboardManager' not in phone and 'getPrimaryClip' not in phone
assert 'mHomeButton.setOnLongClickListener(null)' in phone
assert 'setClickCallback(' in phone
assert 'onNavigationStateChanged()' in phone
assert 'removeObserver(mSandiumNavigationObserver)' in phone
assert 'findViewById(R.id.sandium_shields_row)' in phone
assert 'mToolbarButtonsContainer.getChildAt(0)' not in phone
assert '@Nullable org.chromium.chrome.browser.tab.Tab' not in phone
assert 'org.chromium.chrome.browser.tab.@Nullable Tab mSandiumObservedTab' in phone
assert 'mHomeButton.setAlpha' not in phone
assert 'setHasSpaceToShow(true)' in phone
brave=m.brave((a.core/m.BRAVE).read_text())
assert 'R.id.new_incognito_tab_menu_id : R.id.new_tab_menu_id' in brave
assert 'mBraveShieldsButton.setOnClickListener(this)' in brave
assert 'showShieldsMenu();' in brave
assert 'getMenuOrKeyboardActionController()' in brave
# Unknown upstream shapes fail rather than partially producing a broken toolbar.
try: m.layout('<layout/>')
except ValueError: pass
else: raise AssertionError('Missing Brave include did not fail closed')
print('PASS: pinned transformations, idempotence, resource XML, action/omnibox contracts. NOT compiled/device-tested.')
