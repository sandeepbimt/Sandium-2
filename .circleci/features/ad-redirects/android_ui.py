"""Add the profile switch and site override after the compact Shields layout is composed."""
import argparse
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as ET


SETTINGS_XML = 'android/java/brave-res/xml/brave_privacy_preferences.xml'
SETTINGS = 'android/java/org/chromium/chrome/browser/privacy/settings/BravePrivacySettings.java'
PANEL_XML = 'android/java/brave-res/layout/brave_shields_tab_content.xml'
PANEL = 'android/java/org/chromium/chrome/browser/shields/BraveUnifiedPanelHandler.java'
STRINGS = 'browser/ui/android/strings/android_brave_strings.grd'
A = '{http://schemas.android.com/apk/res/android}'
for prefix, uri in [('android', A[1:-1]), ('app', 'http://schemas.android.com/apk/res-auto'),
                    ('tools', 'http://schemas.android.com/tools')]:
    ET.register_namespace(prefix, uri)


def before(source, anchor, addition, marker):
    """Insert only at the pinned anchor, accepting its complete previous result."""
    if source.count(anchor) != 1:
        raise ValueError('Unexpected Android source near ' + anchor.strip()[:80])
    if marker in source:
        if source.count(marker) != 1 or addition + anchor not in source:
            raise ValueError('Incomplete ad redirects UI near ' + marker)
        return source
    return source.replace(anchor, addition + anchor, 1)


def settings_xml(source):
    return before(source, '''        <org.chromium.components.browser_ui.settings.ChromeSwitchPreference
            android:key="scripts_block"''', '''        <org.chromium.components.browser_ui.settings.ChromeSwitchPreference
            android:key="sandium_block_ad_redirects"
            android:title="@string/sandium_ad_redirects_title"
            android:summary="@string/sandium_ad_redirects_summary"
            android:persistent="false" />
''', 'android:key="sandium_block_ad_redirects"')


def settings_java(source):
    source = before(source, '        PREF_DE_AMP,\n', '        "sandium_block_ad_redirects",\n',
                    '"sandium_block_ad_redirects",')
    return before(source, '        // Debounce\n', '''        ChromeSwitchPreference adRedirects = findPreference("sandium_block_ad_redirects");
        if (adRedirects != null) {
            adRedirects.setChecked(BravePrefServiceBridge.isAdRedirectBlockingEnabled(getProfile()));
            adRedirects.setOnPreferenceChangeListener((preference, value) -> {
                BravePrefServiceBridge.setAdRedirectBlockingEnabled(getProfile(), (boolean) value);
                return true;
            });
        }

''', 'ChromeSwitchPreference adRedirects =')


def panel_xml(source):
    root = ET.fromstring(source)
    controls = root.find(f".//*[@{A}id='@+id/advanced_options_content']")
    if controls is None or len(controls) < 3 or controls[0].get(A+'id') != '@+id/trackers_item':
        raise ValueError('Expected the compact Shields ads and trackers card')
    row = deepcopy(controls[0])
    label = row.find('TextView')
    divider = controls[1]
    if label is None or divider.tag != 'View' or divider.get(A+'id') is not None:
        raise ValueError('Unexpected compact Shields row or divider')
    row.set(A+'id', '@+id/sandium_ad_redirects_item')
    label.set(A+'text', '@string/sandium_ad_redirects_title')
    existing = root.findall(f".//*[@{A}id='@+id/sandium_ad_redirects_item']")
    if existing:
        if existing != [controls[2]] or ET.tostring(controls[2]) != ET.tostring(row):
            raise ValueError('Unexpected existing ad redirects row')
        return source
    controls.insert(2, row)
    controls.insert(3, deepcopy(divider))
    ET.indent(root, space='    ')
    return source[:source.index('<LinearLayout')] + ET.tostring(root, encoding='unicode') + '\n'


BIND_SITE = '''    private boolean isSandiumAdRedirectSiteCurrent(
            Tab tab, Profile profile, WebContents contents, GURL origin) {
        return tab == mCurrentTab && !tab.isDestroyed() && tab.getWebContents() == contents
                && !contents.isDestroyed() && !profile.shutdownStarted()
                && origin.equals(contents.getLastCommittedUrl().getOrigin());
    }

    private void bindSandiumAdRedirects(View row) {
        final Tab tab = mCurrentTab;
        final Profile profile = mProfile;
        final Context context = mContext;
        final WebContents contents = tab == null ? null : tab.getWebContents();
        if (tab == null || contents == null || contents.isDestroyed() || profile == null
                || profile.shutdownStarted() || context == null) {
            row.setEnabled(false);
            return;
        }
        final GURL url = contents.getLastCommittedUrl();
        if (!url.isValid() || !("https".equals(url.getScheme()) || "http".equals(url.getScheme()))) {
            row.setEnabled(false);
            return;
        }
        final GURL origin = url.getOrigin();
        row.setOnClickListener(v -> {
            if (!isSandiumAdRedirectSiteCurrent(tab, profile, contents, origin)) return;
            final int[] values = {BravePrefServiceBridge.AD_REDIRECT_DEFAULT,
                    BravePrefServiceBridge.AD_REDIRECT_BLOCK, BravePrefServiceBridge.AD_REDIRECT_ALLOW};
            final boolean global = BravePrefServiceBridge.isAdRedirectBlockingEnabled(profile);
            final CharSequence[] choices = {
                    context.getText(global ? R.string.sandium_ad_redirects_default_on
                                           : R.string.sandium_ad_redirects_default_off),
                    context.getText(R.string.sandium_ad_redirects_block),
                    context.getText(R.string.sandium_ad_redirects_allow)};
            final int saved = BravePrefServiceBridge.getAdRedirectSiteSetting(profile, url);
            int selected = saved == values[1] ? 1 : saved == values[2] ? 2 : 0;
            new AlertDialog.Builder(context)
                    .setTitle(context.getString(R.string.sandium_ad_redirects_site_title, url.getHost()))
                    .setSingleChoiceItems(choices, selected, (dialog, which) -> {
                        if (isSandiumAdRedirectSiteCurrent(tab, profile, contents, origin)) {
                            BravePrefServiceBridge.setAdRedirectSiteSetting(profile, url, values[which]);
                        }
                        dialog.dismiss();
                    })
                    .setNegativeButton(R.string.brave_cancel, null)
                    .show();
        });
    }

'''


def panel_java(source):
    source = before(source, 'import org.chromium.url.GURL;\n',
                    'import org.chromium.chrome.browser.preferences.BravePrefServiceBridge;\n'
                    'import org.chromium.content_public.browser.WebContents;\n',
                    'import org.chromium.chrome.browser.preferences.BravePrefServiceBridge;')
    source = before(source, '        setupAdvancedOptionsListeners();\n',
                    '        bindSandiumAdRedirects(popupView.findViewById(R.id.sandium_ad_redirects_item));\n',
                    'bindSandiumAdRedirects(popupView.')
    return before(source, '    private void setupAdvancedOptionsListeners() {', BIND_SITE,
                  'private void bindSandiumAdRedirects(')


def strings(source):
    messages = (
        ('TITLE', 'Name of the Shields preference for unwanted ad tabs.', 'Block ad redirects'),
        ('SUMMARY', 'Summary of the ad tab protection setting.',
         'Stop sites from opening unwanted ad tabs when you tap.'),
        ('SITE_TITLE', 'Title of the per-site ad redirects dialog. SITE is the current site.',
         'Block ad redirects on <ph name="SITE">%1$s<ex>example.org</ex></ph>'),
        ('DEFAULT_ON', 'Site follows the enabled global ad tab protection.', 'Use global setting (on)'),
        ('DEFAULT_OFF', 'Site follows the disabled global ad tab protection.', 'Use global setting (off)'),
        ('BLOCK', 'Always block unwanted ad tabs on this site.', 'Block on this site'),
        ('ALLOW', 'Allow unwanted ad tabs on this site.', 'Allow on this site'),
    )
    block = ''.join(f'      <message name="IDS_SANDIUM_AD_REDIRECTS_{name}" desc="{desc}">\n'
                    f'        {label}\n      </message>\n' for name, desc, label in messages)
    return before(source, '      <message name="IDS_TRACKERS_BLOCKED_TEXT"', block,
                  'name="IDS_SANDIUM_AD_REDIRECTS_TITLE"')


def apply(core):
    transforms = {SETTINGS_XML: settings_xml, SETTINGS: settings_java, PANEL_XML: panel_xml,
                  PANEL: panel_java, STRINGS: strings}
    outputs = {core / name: transform((core / name).read_text())
               for name, transform in transforms.items()}
    for path, source in outputs.items():
        if path.read_text() != source:
            path.write_text(source)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('core', type=Path)
    apply(parser.parse_args().core)
