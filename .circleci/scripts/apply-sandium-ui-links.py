#!/usr/bin/env python3
"""Remove audited Brave outbound UI affordances, not browsing or service URLs."""
import argparse
import hashlib
from pathlib import Path

BASE = 'android/java/org/chromium/chrome/browser/'
PATHS = [BASE + p for p in (
    'settings/BraveSettingsActivity.java',
    'settings/BraveWebrtcPolicyPreference.java',
    'settings/BackgroundImagesPreferences.java',
    'privacy/settings/BravePrivacySettings.java',
    'shields/CreateCustomFiltersFragment.java',
    'onboarding/v2/HighlightDialogFragment.java',
    'upgrade/NotificationIntent.java')]

def replace(p, old, new):
    s = p.read_text()
    if new in s: return
    if s.count(old) != 1: raise RuntimeError(f'UI link anchor drift: {p}: {old[:90]!r}')
    p.write_text(s.replace(old, new, 1))

def guarded_body(p, source, start, end, replacement, digest):
    original = source[start:end]
    if original != replacement and hashlib.sha256(original.encode()).hexdigest() != digest:
        raise RuntimeError(f'UI link method body drift: {p}')
    p.write_text(source[:start] + replacement + source[end:])

def apply(core):
    settings = core / PATHS[0]
    # Fragment menu providers can add help after Activity.onPrepareOptionsMenu.
    # Filter after super.onPreparePanel, i.e. after fragment dispatch, every time.
    anchor = '    @Override\n    public boolean onOptionsItemSelected(MenuItem item) {'
    addition = '''    // Sandium: remove outbound support affordances after fragment menu dispatch.
    @Override
    public boolean onPreparePanel(int featureId, android.view.View view, Menu menu) {
        boolean prepared = super.onPreparePanel(featureId, view, menu);
        if (menu != null) removeSandiumSupportItems(menu);
        return prepared;
    }

    private void removeSandiumSupportItems(Menu menu) {
        for (int i = menu.size() - 1; i >= 0; i--) {
            MenuItem item = menu.getItem(i);
            String name;
            try {
                name = getResources().getResourceEntryName(item.getItemId());
            } catch (android.content.res.Resources.NotFoundException ignored) {
                continue;
            }
            if ("menu_id_general_help".equals(name)
                    || "menu_id_targeted_help".equals(name)
                    || "menu_id_site_settings_help".equals(name)
                    || "help_menu_id".equals(name)) {
                menu.removeItem(item.getItemId());
            } else if (item.hasSubMenu()) {
                removeSandiumSupportItems(item.getSubMenu());
            }
        }
    }

'''
    replace(settings, anchor, addition + anchor)
    webrtc = core / PATHS[1]
    s = webrtc.read_text()
    start = s.find('        mLearnMore.setOnClickListener(new View.OnClickListener() {')
    if start >= 0:
        end = s.index('        });', start) + len('        });')
        s = s[:start] + '''        // Sandium: keep all policy choices, remove outbound support affordance.
        mLearnMore.setOnClickListener(null);
        mLearnMore.setVisibility(View.GONE);''' + s[end:]
        webrtc.write_text(s)
    elif 'mLearnMore.setVisibility(View.GONE);' not in s:
        raise RuntimeError('WebRTC support anchor drift')
    replace(core / PATHS[2],
        'if (mLearnMorePreference != null && rewardsDisabledByPolicy) {',
        'if (mLearnMorePreference != null) { // Sandium: no sponsored support link')
    # Preserve warning wording and emphasis; eliminate only the clickable span.
    privacy = core / PATHS[3]
    s = privacy.read_text()
    start = s.find('                                    new ChromeClickableSpan(', s.find('if (mBlockCrosssiteCookiesLearnMore != null)'))
    if start >= 0:
        end = s.index('                                            })))', start) + len('                                            })))')
        s = s[:start] + '''                                    new android.text.style.StyleSpan(
                                            android.graphics.Typeface.NORMAL)))''' + s[end:]
        privacy.write_text(s)
    elif 'android.graphics.Typeface.NORMAL)))' not in s:
        raise RuntimeError('Cookie support span anchor drift')
    filters = core / PATHS[4]
    s = filters.read_text()
    start = s.find('        if (getActivity() != null) {\n            ChromeClickableSpan summaryTextClickableSpan')
    if start >= 0:
        end = s.index('            tvSummary.setText(summaryTextSpannableString);\n        }', start) + len('            tvSummary.setText(summaryTextSpannableString);\n        }')
        s = s[:start] + '''        // Sandium: retain filter syntax guidance as plain, non-clickable text.
        tvSummary.setMovementMethod(null);
        tvSummary.setText(summaryTextSpannableString);''' + s[end:]
        filters.write_text(s)
    elif 'tvSummary.setMovementMethod(null);' not in s:
        raise RuntimeError('Filter syntax link anchor drift')

    tutorial = core / PATHS[5]
    s = tutorial.read_text()
    start = s.find('    private void checkAndOpenNtpPage() {')
    end = s.index('\n    }', start) + len('\n    }')
    replacement = """    private void checkAndOpenNtpPage() {
        // Sandium: dismiss onboarding without opening the Brave tutorial website.
    }"""
    if start < 0: raise RuntimeError('tutorial anchor drift')
    guarded_body(tutorial, s, start, end, replacement, 'fb4261d85e9779d1ea246d59547bed68fc8033d0b57d2da636e34b2572dac844')
    # This notification exclusively advertises a Brave release and opens its support page.
    # Do not affect download, site, safety or other app notification channels.
    notification = core / PATHS[6]
    s = notification.read_text()
    start = s.find('    public static void fireNotificationIfNecessary(Context context) {')
    end = s.index('\n    private static boolean shouldNotify', start)
    replacement = """    public static void fireNotificationIfNecessary(Context context) {
        // Sandium: no outbound Brave-release promotional notification.
    }
"""
    if start < 0: raise RuntimeError('notification anchor drift')
    guarded_body(notification, s, start, end, replacement, '82e4643b56790c5a951dce741ad14f36b8b4b090a35b878a36fe8fe852febc93')

CONNECTION = 'components/page_info/android/java/src/org/chromium/components/page_info/ConnectionInfoView.java'

def apply_chromium(src):
    p = src / CONNECTION
    s = p.read_text()
    start = s.find('    private void addMoreInfoLink(String linkText) {')
    if start < 0: raise RuntimeError('connection-info anchor drift')
    end = s.index('\n    }', start) + len('\n    }')
    # CalledByNative entry remains. Certificate details, warnings and reset controls
    # are distinct sections and remain intact. Only the external help row is omitted.
    replacement = """    private void addMoreInfoLink(String linkText) {
        // Sandium: retain local security information, omit external support link.
    }"""
    guarded_body(p, s, start, end, replacement, '4d328ec9758233a77c406ae398fb90e18c1d2b2c5ae1a04bc5a19d973c4633ac')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--src', type=Path, required=True)
    args = parser.parse_args()
    apply(args.core)
    apply_chromium(args.src)
    print('SANDIUM_UI_LINKS=PASS audited_settings_affordances_removed=true')
