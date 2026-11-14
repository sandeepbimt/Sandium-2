#!/usr/bin/env python3
"""Pinned, idempotent Sandium grouped Shields popup. UI only; no policy writes."""
from pathlib import Path
import argparse
import re
import subprocess
import xml.etree.ElementTree as ET

PIN = '44a84b1f89d9a35287289d6a3d493e362f5a5123'
LAYOUT = 'android/java/brave-res/layout/brave_shields_tab_content.xml'
JAVA = 'android/java/org/chromium/chrome/browser/shields/BraveUnifiedPanelHandler.java'
STRINGS = 'browser/ui/android/strings/android_brave_strings.grd'
MARKER = 'SANDIUM_GROUPED_POPUP_V1'
A = '{http://schemas.android.com/apk/res/android}'
for p, u in [('android', A[1:-1]), ('app', 'http://schemas.android.com/apk/res-auto'), ('tools', 'http://schemas.android.com/tools')]:
    ET.register_namespace(p, u)


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected unique popup anchor: ' + old[:100])
    return text.replace(old, new, 1)


def compact_header(text):
    """Migrate both fresh and already-grouped checkpoint layouts without scaling hit areas."""
    root = ET.fromstring(text)
    nodes = {e.get(A+'id', '').removeprefix('@+id/'): e for e in root.iter()}
    for name, attrs in {
        'site_text_unified': {'textSize': '16sp', 'lineHeight': '22sp'},
        'shields_status_text': {'textSize': '13sp', 'lineHeight': '18sp',
                                'maxLines': '2', 'textColor': '?attr/colorOnSurfaceVariant'},
        'shields_toggle_switch': {'scaleX': '1', 'scaleY': '1', 'minWidth': '48dp',
                                  'minHeight': '48dp', 'layout_marginStart': '12dp',
                                  'layout_marginEnd': '0dp'},
    }.items():
        if name not in nodes:
            raise ValueError('Missing compact header control: '+name)
        for key, value in attrs.items():
            nodes[name].set(A+key, value)
    ET.indent(root, space='    ')
    return text[:text.index('<LinearLayout')] + ET.tostring(root, encoding='unicode')+'\n'


def layout(text):
    if MARKER in text:
        return compact_header(text)
    root = ET.fromstring(text)
    def byid(name):
        matches = [e for e in root.iter() if e.get(A+'id') == '@+id/'+name]
        if len(matches) != 1:
            raise ValueError('Expected unique layout id: '+name)
        return matches[0]
    def detach(e):
        for p in root.iter():
            if e in list(p):
                p.remove(e)
                return e
        raise ValueError('Missing parent')
    def setattrs(e, **attrs):
        for k,v in attrs.items():
            e.set(A+k, v)
        return e
    def group():
        e = ET.Element('LinearLayout')
        return setattrs(e, layout_width='match_parent', layout_height='wrap_content', orientation='vertical',
                        layout_marginTop='10dp', background='@drawable/advanced_options_bg', clipToOutline='true')
    # Preserve all legacy IDs in an invisible container: Java and shared resource references remain
    # valid, but removed controls cannot be focused or activated. No stored setting is changed.
    header = root[0][0]
    detach(header)
    setattrs(header, paddingVertical='16dp')
    byid_cache = {n:byid(n) for n in ['advanced_options_content','advanced_options_container',
        'trackers_item','cookies_item','block_element_item','clear_blocked_elements_button',
        'clear_blocked_elements_divider','shred_data_item','block_count_text']}
    controls = byid_cache['advanced_options_content']
    retained = {}
    for n in ['trackers_item','cookies_item','block_element_item','clear_blocked_elements_button',
              'clear_blocked_elements_divider','shred_data_item']:
        retained[n] = detach(byid_cache[n])
    detach(controls)
    footer = detach(byid_cache['block_count_text'])
    old_children = list(root)
    root.clear()
    setattrs(root, id='@+id/shields_content_container', layout_width='match_parent',
             layout_height='wrap_content', orientation='vertical', padding='16dp')
    title = ET.SubElement(root, 'TextView')
    setattrs(title, layout_width='match_parent', layout_height='wrap_content', text='@string/sandium_shields_title',
             textSize='20sp', fontFamily='sans-serif-medium', textColor='?attr/colorOnSurface',
             accessibilityHeading='true', paddingStart='8dp', paddingEnd='8dp')
    root.append(header)
    hidden = ET.Element('LinearLayout')
    setattrs(hidden, layout_width='0dp', layout_height='0dp', orientation='vertical',
             visibility='gone', importantForAccessibility='noHideDescendants')
    for c in old_children:
        hidden.append(c)
    for c in list(controls):
        controls.remove(c)
        hidden.append(c)
    setattrs(controls, visibility='visible')
    root.append(controls)
    for names in [('trackers_item','cookies_item'),
                  ('block_element_item','clear_blocked_elements_divider','clear_blocked_elements_button'),
                  ('shred_data_item',)]:
        card = group()
        controls.append(card)
        for name in names:
            e = retained[name]
            if name != 'clear_blocked_elements_divider':
                setattrs(e, minHeight='48dp')
            if name == 'clear_blocked_elements_button':
                setattrs(e, textColor='?attr/colorPrimary')
            card.append(e)
    setattrs(footer, layout_width='match_parent', layout_height='wrap_content', textSize='12sp',
             gravity='center', paddingTop='14dp', paddingBottom='2dp',
             accessibilityLiveRegion='none', importantForAccessibility='yes')
    root.append(footer)
    root.append(hidden)
    ET.indent(root, space='    ')
    # Keep upstream license header.
    prefix = text[:text.index('<LinearLayout')]
    return compact_header(prefix + '<!-- '+MARKER+' -->\n' + ET.tostring(root, encoding='unicode')+'\n')


def java(text):
    if MARKER in text:
        return text
    start = text.index('        mBlockCountText.setText(R.string.trackers_blocked_text);')
    end = text.index('        updateAdvancedOptionsSwitches(isShieldsUp);', start)
    text = text[:start] + '        updateSandiumBlockedCount();\n\n' + text[end:]
    # Existing native event dispatch stays intact; calculate at execution time to avoid stale tab
    # counts, and recheck tab identity after posting to the UI thread.
    text = once(text, '            int totalBlocked = getTotalBlockedCount(tabId);\n', '')
    text = once(text, '                        if (isShowing() && mBlockCountNumber != null) {\n                            mBlockCountNumber.setText(String.valueOf(totalBlocked));',
        '                        if (isShowing() && mCurrentTab != null\n                                && mCurrentTab.getId() == tabId) {\n                            updateSandiumBlockedCount();')
    text = once(text, '        mTabsStat.put(tabId, new BlockersInfo());\n    }',
        '        mTabsStat.put(tabId, new BlockersInfo());\n        if (isShowing() && mCurrentTab != null && mCurrentTab.getId() == tabId) {\n            updateSandiumBlockedCount();\n        }\n    }')
    text = once(text, '        setupAdvancedOptionsListeners();\n    }',
        '        setupAdvancedOptionsListeners();\n        applySandiumPopupVisibility();\n    }')
    # Pin all direct-control state, including returning from submenus and Shields off/on.
    text = once(text, '    private void showReportBrokenSitePanel() {', '''    // SANDIUM_GROUPED_POPUP_V1: presentation only; do not change protection preferences.
    private void applySandiumPopupVisibility() {
        if (mAdvancedOptionsButton != null) mAdvancedOptionsButton.setVisibility(View.GONE);
        if (mAdvancedOptionsContent != null) mAdvancedOptionsContent.setVisibility(View.VISIBLE);
        mIsAdvancedOptionsExpanded = true;
        if (mReportBrokenSiteSection != null) mReportBrokenSiteSection.setVisibility(View.GONE);
        if (mShieldsWarningSection != null) mShieldsWarningSection.setVisibility(View.GONE);
    }

    private void updateSandiumBlockedCount() {
        if (mContext == null || mBlockCountText == null) return;
        int tabId = mCurrentTab != null ? mCurrentTab.getId() : -1;
        long count = (long) getAdsBlockedCount(tabId) + getTrackersBlockedCount(tabId);
        String formatted = java.text.NumberFormat.getIntegerInstance().format(count);
        mBlockCountText.setText(mContext.getString(R.string.sandium_shields_blocked_count, formatted));
        mBlockCountText.setTextColor(ContextCompat.getColor(mContext,
                count == 0 ? R.color.sandium_shields_count_zero : R.color.sandium_shields_count_positive));
    }

    private void showReportBrokenSitePanel() {''')
    text = once(text, '            mShieldIconUnified.setColorFilter(new ColorMatrixColorFilter(matrix));\n        }\n    }',
        '            mShieldIconUnified.setColorFilter(new ColorMatrixColorFilter(matrix));\n        }\n        applySandiumPopupVisibility();\n    }')
    text = once(text, '        updateResetButtonState();\n    }\n\n    private void showHttpsUpgradePanel()',
        '        updateResetButtonState();\n        updateClearBlockedElementsState();\n        applySandiumPopupVisibility();\n    }\n\n    private void showHttpsUpgradePanel()')
    # Keep clear action discoverable but disabled when nothing can be cleared.
    text = once(text, '''        int visibility = hasBlockedElements ? View.VISIBLE : View.GONE;
        mClearBlockedElementsButton.setVisibility(visibility);
        mClearBlockedElementsDivider.setVisibility(visibility);''', '''        mClearBlockedElementsButton.setVisibility(View.VISIBLE);
        mClearBlockedElementsButton.setEnabled(hasBlockedElements);
        mClearBlockedElementsButton.setAlpha(hasBlockedElements ? 1f : 0.5f);
        mClearBlockedElementsDivider.setVisibility(View.VISIBLE);''')
    return text


def strings(text):
    if 'name="IDS_SANDIUM_SHIELDS_TITLE"' in text:
        return text
    return once(text, '      <message name="IDS_TRACKERS_BLOCKED_TEXT"', '''      <message name="IDS_SANDIUM_SHIELDS_TITLE" desc="Title of the Sandium site protection popup.">
        Sandium Shields
      </message>
      <message name="IDS_SANDIUM_SHIELDS_BLOCKED_COUNT" desc="Single subtle line in the site protection popup. COUNT is a localized number of blocked trackers and ads, excluding scripts and fingerprinting.">
        <ph name="COUNT">%1$s<ex>23</ex></ph> trackers and ads blocked
      </message>
      <message name="IDS_TRACKERS_BLOCKED_TEXT"''')


def colors(text, zero, positive):
    for name, value in [('sandium_shields_count_zero', zero), ('sandium_shields_count_positive', positive)]:
        if 'name="'+name+'"' not in text:
            text = once(text, '</resources>', f'    <color name="{name}">{value}</color>\n</resources>')
    return text


COLOR_FILES = ('java/brave-res/values/sandium_shields_colors.xml',
               'java/brave-res/values-night/sandium_shields_colors.xml')

def register_colors(text):
    anchor = '    "java/brave-res/values/brave_ids.xml",\n'
    for path in COLOR_FILES:
        entry = '    "'+path+'",\n'
        if entry not in text:
            text = once(text, anchor, anchor+entry)
        if text.count(entry) != 1:
            raise ValueError('Duplicate popup color source: '+path)
    return text


def validate_layout(text):
    root = ET.fromstring(text)
    parents = {c:p for p in root.iter() for c in p}
    nodes = {e.get(A+'id','').removeprefix('@+id/'):e for e in root.iter() if e.get(A+'id')}
    def hidden(e):
        while e is not None:
            if e.get(A+'visibility') == 'gone': return True
            e = parents.get(e)
        return False
    for n in ['trackers_item','cookies_item','block_element_item','clear_blocked_elements_button','shred_data_item','shields_toggle_switch','block_count_text']:
        if n not in nodes or hidden(nodes[n]): raise ValueError('Missing visible control: '+n)
    for n in ['https_upgrade_item','scripts_toggle','fingerprinting_toggle','global_settings_item','shields_warning_section','advanced_options_button','block_count_number']:
        if n not in nodes or not hidden(nodes[n]): raise ValueError('Unexpected visible control: '+n)
    if list(root)[-2] is not nodes['block_count_text']:
        raise ValueError('Counter must be the last visible child')


def apply(core):
    sha = subprocess.check_output(['git','-C',str(core),'rev-parse','HEAD'], text=True).strip()
    if sha != PIN:
        raise ValueError('Wrong Brave source pin: '+sha)
    changes = {core/LAYOUT:layout((core/LAYOUT).read_text()),
               core/JAVA:java((core/JAVA).read_text()), core/STRINGS:strings((core/STRINGS).read_text())}
    for folder, zero, positive in [('values','#795900','#365B40'),('values-night','#E9D58B','#B7D9BE')]:
        p = core/('android/java/brave-res/'+folder+'/sandium_shields_colors.xml')
        changes[p] = colors('<resources>\n</resources>\n', zero, positive)
        # Clean up old misplaced definitions from checkpointed overlay inputs.
        overlay = core/('android/java/res/'+folder+'/brave_colors.xml')
        changes[overlay] = re.sub(r'    <color name="sandium_shields_count_(?:zero|positive)">[^<]*</color>\n', '', overlay.read_text())
    build = core/'android/BUILD.gn'
    changes[build] = register_colors(build.read_text())
    for path, old, new in [
        ('android/java/brave-res/drawable/advanced_options_bg.xml', '?attr/colorSurface', '?attr/colorSurfaceContainer'),
        ('android/java/brave-res/drawable/unified_panel_background.xml', '?attr/colorSurfaceContainer', '?attr/colorSurfaceContainerLowest')]:
        p = core/path
        s = p.read_text()
        if 'android:color="'+new+'"' not in s:
            s = once(s, 'android:color="'+old+'"', 'android:color="'+new+'"')
        changes[p] = s
    validate_layout(changes[core/LAYOUT])
    if '%1$s' not in changes[core/STRINGS]: raise ValueError('Android string format missing')
    for p,s in changes.items():
        if p.suffix in ('.xml','.grd'):
            ET.fromstring(s)
    for p,s in changes.items():
        if not p.exists() or p.read_text()!=s:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(s)
    print('SANDIUM_GROUPED_POPUP=PASS controls=direct count=ads+trackers protections=unchanged')

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('core', type=Path)
    apply(p.parse_args().core)
