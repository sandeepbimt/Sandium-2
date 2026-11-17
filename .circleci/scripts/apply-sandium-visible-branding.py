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
PROTECTED_ID = re.compile(r'(?:COPYRIGHT|LICENSE|LEGAL|TERMS|PRIVACY_POLICY|CREDITS|ABOUT_VERSION|BRAVE_SEARCH|VPN|WALLET|REWARDS|BRAVE_ADS|BRAVE_NEWS|LEO|AI_CHAT|BRAVE_TALK|ORIGIN|PREMIUM|BRAVE_ACCOUNT|FEEDBACK|SURVEY|CREATE_GOOGLE|MANAGE_GOOGLE|CHANGE_GOOGLE|FIND_MY_PHONE|LEAK_HELP_MESSAGE|PERSONAL_CONTEXT|NTP_MODULES_TASKS_INFO)')
PROTECTED_TEXT = re.compile(r'Brave (?:Software|Authors|Search|VPN|Wallet|Rewards|Ads|News|Leo|Talk|Origin|Premium|Account|Help Center|Community|Cast|Home app|Webstore|Drive|Docs|Sheets|Slides|Calendar|Sites|Keep|Forms|Disability Support|servers|help)|(?:[Cc]opyright|[Ll]icen[cs]e|[Tt]erms of|[Pp]rivacy [Pp]olicy)')
# Provider identities and data-recipient disclosures are not browser branding.
# Inspect readable text (not XML tags) so inline markup cannot split a guard.
PROVIDER_ID = re.compile(
    r'(?:EULA|UMA|METRICS|CRASH_REPORT|AUTOFILL_AI|SUGGESTIONS_FROM_GEMINI|'
    r'COMPOSE_|HISTORY_EMBEDDINGS|CONTEXTUAL_TASKS|STS_SETTINGS|'
    r'POLICY_RISK_TAG_GOOGLE_SHARING|MERCHANT_VIEWER|AUTOFILL_GMAIL_OTP|PIX_ACCOUNT_LINKING|GEMINI|GOOGLE_BOTTOM_BAR|'
    r'MANAGEMENT_.*(?:REPORT|TELEMETRY)|CONTEXTUAL_CUEING|HISTORY_SYNC|RECENT_TABS_SYNC|'
    r'NEW_TAB_OTR_SUBTITLE|DO_NOT_TRACK_SUMMARY_DISCLAIMER|UNIVERSAL_OPT_OUT_INFO_TEXT|'
    r'PAGE_INFO_CHANGE_PASSWORD_DETAILS_SIGNED_IN_NON_SYNC)')
PROVIDER_TEXT = re.compile(
    r"Brave(?:['’]s)? (?:sync chains?|servers?|services?|Browser Cloud Management|"
    r'Enterprise|Advanced Protection|Translate|Pay(?:ments)?|Play|Web Store|'
    r'Photos|Lens|Maps|Meet|DNS|AI|Workspace|Drawings|Jamboard|Apps Script|App Home|'
    r'App Voice|Notifications Platform|Root Store|Sync|Dashboard|Terms|Account)\b|'
    r'(?:sent|send(?:ing)?|shared|shar(?:e|ing)|upload(?:ed|ing)?|'
    r'transmit(?:ted|ting)?|report(?:ed|ing)?)[^.]{0,600}(?:to|with) Brave\b|'
    r'(?:provided|powered|delivered|optimized|managed|owned|operated|developed|stored|reviewed|verified) by Brave\b|'
    r'Discover by Brave\b|'
    r'reviews? from Brave\b|(?:including|notify) Brave\b|'
    r'Brave may personalize\b', re.I)


def protected_message(name, body):
    readable = re.sub(r'\s+', ' ', re.sub(r'<[^>]*>', ' ', body))
    return bool(PROTECTED_ID.search(name) or PROTECTED_TEXT.search(body)
                or PROVIDER_ID.search(name) or PROVIDER_TEXT.search(readable))


MESSAGE = re.compile(r'(<message\b[^>]*\bname="([^"]+)"[^>]*>)(.*?)(</message>)', re.S)


def rebrand_messages(source):
    changed, retained = [], []
    def message(m):
        start, name, body, end = m.groups()
        if not re.search(r'\bBrave\b', body):
            return m.group(0)
        if protected_message(name, body):
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


COPY_MANIFEST = Path(__file__).resolve().parents[1] / 'branding/string-copy-manifest.json'


def branding_copy_manifest(core):
    manifest = json.loads(COPY_MANIFEST.read_text())
    expected = {(x['core'], x['consumed']) for x in manifest['copies']}
    actual = set()
    def visit(canonical, consumed):
        pair = (canonical, consumed)
        if pair in actual:
            return
        actual.add(pair)
        for part in re.findall(r'<part\s+file="([^"]+)"', (core / canonical).read_text()):
            if part == 'chromeos_strings.grdp':
                continue  # same exclusion as pinned Brave l10nUtil.js
            visit((Path(canonical).parent / part).as_posix(),
                  (Path(consumed).parent / part).as_posix())
    for root in manifest['roots']:
        visit(root['core'], root['consumed'])
    if actual != expected:
        raise RuntimeError('Brave string copy inventory drift: '
                           + str(sorted(actual ^ expected)))
    for canonical, consumed in expected:
        if not (core / canonical).is_file() or not (core.parent / consumed).is_file():
            raise RuntimeError('Missing consumed branding resource: ' + consumed)
    return sorted(expected)


def rebrand_consumed_graph(core, verify=False):
    # npm's branding copy runs BEFORE the final product overlay. Fix both the
    # canonical copy source and the already-copied resources used by this build.
    # Do not recopy whole files: that would discard earlier Sandium UI changes.
    pairs = branding_copy_manifest(core)
    paths = {core / canonical for canonical, _ in pairs}
    paths.update(core.parent / consumed for _, consumed in pairs)
    report = {}
    for path in sorted(paths):
        old = path.read_text()
        new, changed, retained = rebrand_messages(old)
        if verify and new != old:
            raise RuntimeError('Unbranded consumed resource: ' + str(path))
        if not verify and new != old:
            path.write_text(new)
        report[str(path.relative_to(core.parent))] = {
            'changed': changed, 'preserved_service_or_legal': retained}
    return report


DEVELOPER_XML = 'android/java/res/xml/developer_preferences.xml'


def rebrand_developer_hint(source):
    pattern = re.compile(r'(android:title="Hint: You can also enable Developer options on '
                         r'Beta/Stable channels by tapping the )(?:Chrome|Brave|Sandium)'
                         r'( version in &quot;Settings > About )(?:Chrome|Brave|Sandium)'
                         r'(&quot; multiple times\.")')
    result, count = pattern.subn(r'\1Sandium\2Sandium\3', source)
    if count != 1:
        raise RuntimeError('Developer options branding hint changed')
    return result


def rebrand_about_titles(source):
    """Patch the consumed Chromium GRD, not only Brave's copy source.

    Brave copies its canonical GRD before this final identity pass. Updating
    core alone leaves the current build's Settings/About labels as Brave.
    Keep copyright/legal messages untouched and reject ambiguous source drift.
    """
    for name in ('IDS_PREFS_ABOUT_CHROME', 'IDS_MENU_ABOUT_CHROME'):
        pattern = re.compile(r'(<message\b(?=[^>]*\bname="' + name
                             + r'")[^>]*>)(.*?)(</message>)', re.S)
        matches = list(pattern.finditer(source))
        if len(matches) != 1:
            raise RuntimeError('expected one About title: ' + name)
        match = matches[0]
        body = match.group(2)
        if body.strip() not in ('About Chrome', 'About Brave', 'About Sandium'):
            raise RuntimeError('unrecognized About title: ' + name)
        replacement = re.sub(r'About (?:Chrome|Brave|Sandium)', 'About Sandium', body)
        source = source[:match.start(2)] + replacement + source[match.end(2):]
    return source


ABOUT_JAVA = 'chrome/android/java/src/org/chromium/chrome/browser/about_settings/AboutChromeSettings.java'
LEGAL_JAVA = 'chrome/android/java/src/org/chromium/chrome/browser/about_settings/LegalInformationSettings.java'
COPYRIGHT_BLOCK = """        Calendar calendar = CalendarFactory.get();
        calendar.setTimeInMillis(System.currentTimeMillis());
        int currentYear = calendar.get(Calendar.YEAR);
        p.setSummary(getString(R.string.legal_information_summary, currentYear));"""
COPYRIGHT_CLEARED = """        // Sandium: retain the Legal information link; show attribution inside it.
        p.setSummary(null);"""
LEGAL_ANCHOR = '        mPageTitle.set(getString(R.string.legal_information_title));'
LEGAL_NOTICE = """
        // SANDIUM_LEGAL_NOTICE: preserve the exact upstream copyright resource,
        // year formatting and all existing license/terms links one tap away.
        androidx.preference.Preference copyright =
                new androidx.preference.Preference(requireContext());
        copyright.setKey("sandium_copyright_notice");
        copyright.setSelectable(false);
        copyright.setOrder(-1);
        java.util.Calendar calendar =
                org.chromium.components.browser_ui.util.date.CalendarFactory.get();
        calendar.setTimeInMillis(System.currentTimeMillis());
        copyright.setTitle(getString(R.string.legal_information_summary,
                calendar.get(java.util.Calendar.YEAR)));
        getPreferenceScreen().addPreference(copyright);"""


ABOUT_FOOTER_ANCHOR = "    @Override\n    public MonotonicObservableSupplier<String> getPageTitle()"
ABOUT_FOOTER = """    // SANDIUM_LEGAL_FOOTER: small visible text, full accessible one-tap target.
    @Override
    public android.view.View onCreateView(android.view.LayoutInflater inflater,
            @Nullable android.view.ViewGroup container, @Nullable Bundle savedInstanceState) {
        android.view.View preferences = super.onCreateView(inflater, container, savedInstanceState);
        assumeNonNull(preferences);
        android.content.Context context = requireContext();
        float density = context.getResources().getDisplayMetrics().density;
        android.widget.LinearLayout root = new android.widget.LinearLayout(context);
        root.setOrientation(android.widget.LinearLayout.VERTICAL);
        root.addView(preferences, new android.widget.LinearLayout.LayoutParams(
                android.view.ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        android.widget.TextView legal = new android.widget.TextView(context);
        legal.setText(R.string.legal_information_title);
        legal.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 12);
        android.content.res.TypedArray colors = context.obtainStyledAttributes(
                new int[] {android.R.attr.textColorSecondary,
                        android.R.attr.selectableItemBackground});
        try {
            android.content.res.ColorStateList secondary = colors.getColorStateList(0);
            if (secondary != null) legal.setTextColor(secondary);
            legal.setBackgroundResource(colors.getResourceId(1, 0));
        } finally {
            colors.recycle();
        }
        legal.setGravity(android.view.Gravity.CENTER);
        legal.setMinHeight(Math.round(48 * density));
        legal.setPadding(Math.round(16 * density), Math.round(8 * density),
                Math.round(16 * density), Math.round(8 * density));
        legal.setFocusable(true);
        legal.setOnClickListener(v ->
                org.chromium.chrome.browser.settings.SettingsNavigationFactory
                        .createSettingsNavigation(context)
                        .startSettings(context, LegalInformationSettings.class));
        root.addView(legal, new android.widget.LinearLayout.LayoutParams(
                android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                android.view.ViewGroup.LayoutParams.WRAP_CONTENT));
        return root;
    }

"""


def compact_legal_footer(about):
    if '// SANDIUM_LEGAL_FOOTER:' in about:
        return about
    if about.count(COPYRIGHT_CLEARED) != 1 or about.count(ABOUT_FOOTER_ANCHOR) != 1:
        raise RuntimeError('About legal footer anchors changed')
    about = about.replace(COPYRIGHT_CLEARED, COPYRIGHT_CLEARED +
                          '\n        p.setVisible(false); // Replaced by the bottom one-tap link.')
    return about.replace(ABOUT_FOOTER_ANCHOR, ABOUT_FOOTER + ABOUT_FOOTER_ANCHOR)


def relocate_copyright(about, legal):
    if COPYRIGHT_CLEARED not in about:
        if about.count(COPYRIGHT_BLOCK) != 1:
            raise RuntimeError('About copyright summary anchor changed')
        about = about.replace(COPYRIGHT_BLOCK, COPYRIGHT_CLEARED)
        about = about.replace('import java.util.Calendar;\n', '')
    if LEGAL_NOTICE not in legal:
        if legal.count(LEGAL_ANCHOR) != 1:
            raise RuntimeError('Legal information title anchor changed')
        legal = legal.replace(LEGAL_ANCHOR, LEGAL_ANCHOR + LEGAL_NOTICE)
    # No attribution string, license URL, or legal fragment route is removed.
    return about, legal


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
    report['copied_resource_graph'] = rebrand_consumed_graph(core)
    for hint in (core / DEVELOPER_XML, core.parent / ('chrome/' + DEVELOPER_XML)):
        hint.write_text(rebrand_developer_hint(hint.read_text()))
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
    consumed = core.parent / 'chrome/browser/ui/android/strings/android_chrome_strings.grd'
    old = consumed.read_text()
    new = rebrand_about_titles(old)
    if new != old:
        consumed.write_text(new)
    report['about_titles'] = ['IDS_PREFS_ABOUT_CHROME', 'IDS_MENU_ABOUT_CHROME']
    about_path, legal_path = core.parent / ABOUT_JAVA, core.parent / LEGAL_JAVA
    about, legal = relocate_copyright(about_path.read_text(), legal_path.read_text())
    about = compact_legal_footer(about)
    about_path.write_text(about)
    legal_path.write_text(legal)
    report['copyright_notice'] = 'relocated intact into Legal information'
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
