#!/usr/bin/env python3
"""Final Android browser-identity pass; never rewrite services, URLs or legal text."""
import argparse
import json
import re
import shutil
from pathlib import Path

STRING_FILES = (
    'browser/ui/android/strings/android_brave_strings.grd',
    'browser/ui/android/strings/android_chrome_strings.grd',
    'browser/ui/android/strings/android_chrome_strings_override.grd',
    'components/components_brave_strings.grd',
    'components/components_strings.grd',
    'components/components_strings_override.grd',
    'app/brave_strings.grd',
    'app/brave_strings_override.grd',
)
# These still describe third-party services or mandatory attribution, not our app.
PROTECTED_ID = re.compile(r'(?:COPYRIGHT|LICENSE|LEGAL|TERMS|PRIVACY_POLICY|CREDITS|ABOUT_VERSION|BRAVE_SEARCH|VPN|WALLET|REWARDS|BRAVE_ADS|BRAVE_NEWS|LEO|AI_CHAT|BRAVE_TALK|ORIGIN|PREMIUM|BRAVE_ACCOUNT)')
PROTECTED_TEXT = re.compile(r'Brave (?:Software|Authors|Search|VPN|Wallet|Rewards|Ads|News|Leo|Talk|Origin|Premium|Account)|(?:[Cc]opyright|[Ll]icen[cs]e|[Tt]erms of|[Pp]rivacy [Pp]olicy)')
MESSAGE = re.compile(r'(<message\b[^>]*\bname="([^"]+)"[^>]*>)(.*?)(</message>)', re.S)


def rebrand_messages(source):
    changed, retained = [], []
    def message(m):
        start, name, body, end = m.groups()
        if not re.search(r'\bBrave\b', body):
            return m.group(0)
        if PROTECTED_ID.search(name) or PROTECTED_TEXT.search(body):
            retained.append(name)
            return m.group(0)
        # Placeholders/examples, tags, comments and URL values are not app copy.
        chunks = re.split(r'(<ph\b.*?</ph>|<ex\b.*?</ex>|<!--.*?-->|<[^>]*>|https?://[^\s<>]+)', body, flags=re.S)
        body2 = ''.join(chunk if i % 2 else re.sub(r'\bBrave\b', 'Sandium', chunk)
                        for i, chunk in enumerate(chunks))
        if body2 != body:
            changed.append(name)
        return start + body2 + end
    return MESSAGE.sub(message, source), changed, retained


def mark_drawable(width, height):
    # Preserve the original drawable's intrinsic size. 12% vertical padding and
    # the source logo's 64:77 aspect ratio avoid stretching inside square hosts.
    h = round(height * .76, 2)
    w = round(h * 64 / 77, 2)
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!-- Sandium browser identity. Existing Sandium artwork; not a third-party service logo. -->
<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
    <item android:width="{width}dp" android:height="{height}dp">
        <shape android:shape="rectangle"><solid android:color="@android:color/transparent" /></shape>
    </item>
    <item android:width="{w}dp" android:height="{h}dp" android:gravity="center">
        <bitmap android:src="@drawable/sandium_toolbar_mark" android:gravity="fill" />
    </item>
</layer-list>
'''


def apply(core):
    report = {'changed_messages': {}, 'retained_service_or_legal_messages': {}, 'logo_paths': []}
    for rel in STRING_FILES:
        p = core / rel
        if not p.is_file():
            raise RuntimeError('pinned branding resource missing: ' + rel)
        old = p.read_text()
        new, changed, retained = rebrand_messages(old)
        if new != old:
            p.write_text(new)
        report['changed_messages'][rel] = changed
        report['retained_service_or_legal_messages'][rel] = retained
        if rebrand_messages(new)[0] != new:
            raise RuntimeError('non-idempotent string transformation')
    for rel, width, height in (
        ('android/java/brave-res/drawable/ic_brave_logo.xml', 162, 162),
        ('android/java/res/drawable/chrome_logo_on_circular_background.xml', 31, 31),
    ):
        p = core / rel
        old = p.read_text()
        # Keep the upstream legal comment even when replacing vector art.
        legal = re.search(r'<!-- Copyright.*?-->', old, re.S)
        new = mark_drawable(width, height)
        if legal:
            new = new.replace('<!-- Sandium', legal.group() + '\n<!-- Sandium', 1)
        if old != new:
            p.write_text(new)
        report['logo_paths'].append(rel)
    # The settings lion is the actual Brave Account service, not browser identity.
    # Preserve it along with its service name.
    for rel in ('android/java/res/layout/new_tab_page_incognito.xml',):
        p = core / rel
        old = p.read_text()
        new = old.replace('@drawable/ic_social_brave_release_favicon_fullheight_color',
                          '@drawable/sandium_toolbar_mark')
        if new != old:
            p.write_text(new)
        if 'ic_social_brave_release_favicon_fullheight_color' in new:
            raise RuntimeError('browser logo replacement failed: ' + rel)
        report['logo_paths'].append(rel)
    # Tab-switcher NTP favicons have their own resource module. Register the
    # existing artwork there rather than introducing a dependency on chrome.R.
    favicon = core / 'browser/ui/android/favicon'
    resources = favicon / 'java/res'
    (resources / 'drawable-nodpi').mkdir(parents=True, exist_ok=True)
    (resources / 'drawable').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(core / 'android/java/brave-res/drawable-nodpi/sandium_toolbar_mark.webp',
                    resources / 'drawable-nodpi/sandium_ntp_logo.webp')
    (resources / 'drawable/sandium_ntp_mark.xml').write_text(
        mark_drawable(24, 24).replace('@drawable/sandium_toolbar_mark', '@drawable/sandium_ntp_logo'))
    gn = favicon / 'BUILD.gn'
    content = gn.read_text()
    anchor = 'android_resources("java_resources") {\n'
    source_block = ('  sources = [\n'
                    '    "java/res/drawable-nodpi/sandium_ntp_logo.webp",\n'
                    '    "java/res/drawable/sandium_ntp_mark.xml",\n'
                    '  ]\n')
    if 'java/res/drawable/sandium_ntp_mark.xml' not in content:
        if content.count(anchor) != 1:
            raise RuntimeError('favicon resource target changed')
        gn.write_text(content.replace(anchor, anchor + source_block))
    java = favicon / 'java/src/org/chromium/chrome/browser/ui/favicon/BraveTabListFaviconProvider.java'
    content = java.read_text()
    for name in ('ic_social_brave_outline_favicon_fullheight', 'ic_social_brave_carved_favicon_fullheight'):
        content = content.replace('R.drawable.' + name, 'R.drawable.sandium_ntp_mark')
    original_draw = """        drawable.setBounds(0, 0, size, size);
        drawable.draw(canvas);"""
    scaled_draw = """        // Sandium's raster mark wrapper has an intrinsic dp canvas. Scale
        // the whole drawable, not only its outer bounds, to avoid cropping.
        int intrinsicWidth = Math.max(1, drawable.getIntrinsicWidth());
        int intrinsicHeight = Math.max(1, drawable.getIntrinsicHeight());
        int saveCount = canvas.save();
        canvas.scale((float) size / intrinsicWidth, (float) size / intrinsicHeight);
        drawable.setBounds(0, 0, intrinsicWidth, intrinsicHeight);
        drawable.draw(canvas);
        canvas.restoreToCount(saveCount);"""
    if original_draw not in content and scaled_draw not in content:
        raise RuntimeError('favicon sizing anchor changed')
    content = content.replace(original_draw, scaled_draw)
    java.write_text(content)
    notification = core / 'android/java/org/chromium/chrome/browser/notifications/retention/RetentionNotificationUtil.java'
    content = notification.read_text()
    old = 'private static final String BRAVE_BROWSER = "Brave Browser";'
    new = 'private static final String BRAVE_BROWSER = "Sandium";'
    if old not in content and new not in content:
        raise RuntimeError('notification title anchor changed')
    notification.write_text(content.replace(old, new))
    report['logo_paths'].append('browser/ui/android/favicon:tab-switcher-NTP')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = apply(args.core)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print('SANDIUM_VISIBLE_BRANDING=PASS messages=' + str(sum(map(len, report['changed_messages'].values())))
          + ' logo_paths=' + str(len(report['logo_paths'])))

if __name__ == '__main__':
    main()
