#!/usr/bin/env python3
"""Pinned Chromium 156 native switches: Oppo-inspired color hierarchy, native behavior.
Run after Shields composition. No web content or preference values are modified.
"""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET
BASE = 'components/browser_ui/styles/android'
STYLE = BASE + '/java/res/values/styles.xml'
BUILD = BASE + '/BUILD.gn'
SHIELDS = 'android/java/brave-res/layout/brave_shields_tab_content.xml'
MARKER = '<!-- SANDIUM_OPPO_SWITCH_V1 -->'

def once(text, old, new):
    if new in text:
        return text
    if text.count(old) != 1:
        raise ValueError('Pinned switch anchor changed: ' + old[:80])
    return text.replace(old, new, 1)

def style(text):
    anchor = '    <style name="Widget.BrowserUI.Switch" parent="Widget.Material3.CompoundButton.MaterialSwitch">'
    extra = '''
        <!-- SANDIUM_OPPO_SWITCH_V1 -->
        <item name="thumbTint">@color/sandium_switch_thumb</item>
        <item name="trackTint">@color/sandium_switch_track</item>
        <item name="trackDecorationTint">@android:color/transparent</item>
        <item name="thumbIcon">@null</item>'''
    text = once(text, anchor, anchor + extra)
    # Direct Shields widgets did not use BrowserUI's scale. Share tints, not scale.
    direct = '    <style name="Widget.Sandium.ShieldsSwitch" parent="Widget.Material3.CompoundButton.MaterialSwitch">' + extra + '\n    </style>\n'
    return once(text, '</resources>', direct + '</resources>')

def selector(thumb):
    # Deliberately fixed Oppo switch palette, including dynamic themes. Other
    # controls retain dynamic colors; arbitrary pastel tracks cannot safely use white.
    on = '@android:color/white' if thumb else '#198CFF'
    off = '#E8E8E8' if thumb else '#505050'
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!-- Sandium: preserve checked/disabled states and native switch interaction. -->
<selector xmlns:android="http://schemas.android.com/apk/res/android">
    <item android:state_enabled="false" android:state_checked="true" android:color="{on}" android:alpha="0.38" />
    <item android:state_enabled="false" android:color="{off}" android:alpha="0.38" />
    <item android:state_checked="true" android:color="{on}" />
    <item android:color="{off}" />
</selector>
'''

def shields(text):
    # Shields has direct MaterialSwitch declarations, unlike Settings' common widget.
    tag = '<com.google.android.material.materialswitch.MaterialSwitch'
    import re
    matches = list(re.finditer(tag + r'\b[^>]*>', text))
    if len(matches) != 3:
        raise ValueError('Expected three pinned Shields switches')
    for m in reversed(matches):
        block = m.group()
        expected = 'style="@style/Widget.Sandium.ShieldsSwitch"'
        if expected in block:
            continue
        if re.search(r'\bstyle=', block):
            raise ValueError('Unexpected explicit Shields switch style')
        text = text[:m.start()] + block.replace(tag,tag+'\n                    '+expected,1) + text[m.end():]
    return text

def apply(src, brave):
    result = {src/STYLE: style((src/STYLE).read_text()), brave/SHIELDS: shields((brave/SHIELDS).read_text())}
    build = (src/BUILD).read_text()
    for name in ['thumb','track']:
        path = f'java/res/color/sandium_switch_{name}.xml'
        anchor = '    "java/res/color/bottom_sheet_bg_color.xml",'
        if ('    "'+path+'",') not in build:
            build = once(build, anchor, anchor+'\n    "'+path+'",')
        result[src/BASE/path] = selector(name == 'thumb')
    result[src/BUILD] = build
    for p,t in result.items():
        if p.suffix == '.xml': ET.fromstring(t)
    for p,t in result.items():
        p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t)
    return len(result)

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('src',type=Path);p.add_argument('brave',type=Path);a=p.parse_args()
    print('SANDIUM_OPPO_TOGGLES=PASS files='+str(apply(a.src,a.brave)))
