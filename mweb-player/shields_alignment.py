"""Align the three site switch labels without replacing the native switch controls."""

import hashlib
import re

LAYOUT = 'chrome/android/java/res/layout/raws_global_shield_sheet.xml'
JAVA = 'chrome/android/java/src/org/chromium/chrome/browser/settings/RawsGlobalShieldSheet.java'
OWNERS = {
    LAYOUT: '58d11f8a48acb56f50a582a3dfd2084016fc5ac3d9d0bcf1dff5e14eeddf5939',
    JAVA: '83700a8f85e50b04c998ed2ee1ab88d018005c7ff0423feebf3bbfb83b7db223',
}
SITE_SWITCHES = {
    'raws_shields_ads': 'raws_shields_ads',
    'raws_shields_dark_pages': 'raws_shields_dark_pages',
    'raws_shields_block_cookies': 'raws_shields_third_party_cookies',
}


def once(text: str, before: str, after: str) -> str:
    if text.count(before) != 1:
        raise ValueError(f'missing or ambiguous Shields anchor: {before}')
    return text.replace(before, after, 1)


def _layout(text: str) -> str:
    for switch, label in SITE_SWITCHES.items():
        pattern = (
            r'^            <com\.google\.android\.material\.materialswitch\.MaterialSwitch\b'
            r'[^<>]* android:id="@\+id/' + re.escape(switch) + r'" />$'
        )
        matches = list(re.finditer(pattern, text, re.MULTILINE))
        if len(matches) != 1:
            raise ValueError(f'missing or ambiguous Shields switch: {switch}')
        old = matches[0][0]
        native = once(old.strip(), 'android:layout_height="wrap_content"',
                      'android:layout_height="match_parent"')
        native = once(native,
                      f'android:text="@string/{label}" android:textSize="16sp" '
                      'android:textColor="@color/raws_shields_text"',
                      f'android:contentDescription="@string/{label}"')
        # Keep the measured, full-row switch on top: it alone owns click, drag,
        # checked state and accessibility. Use the action-row TextView metrics
        # and leave an end lane for the existing Material track and label gap.
        row = f'''            <FrameLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:minHeight="48dp" android:importantForAccessibility="no">
                <TextView android:id="@+id/{switch}_label" android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_gravity="center_vertical" android:text="@string/{label}" android:textSize="16sp" android:textColor="@color/raws_shields_text" android:alpha="0.55" android:minHeight="48dp" android:paddingStart="16dp" android:paddingEnd="96dp" android:paddingVertical="4dp" android:gravity="center_vertical" android:clickable="false" android:focusable="false" android:importantForAccessibility="no" />
                {native}
            </FrameLayout>'''
        text = once(text, old, row)
    return text


def _java(text: str) -> str:
    for method, row, label in (
        ('configureDarkPages', 'mDarkSwitch', 'raws_shields_dark_pages_label'),
        ('renderCookies', 'mCookieSwitch', 'raws_shields_block_cookies_label'),
        ('renderSiteAdFiltering', 'row', 'raws_shields_ads_label'),
    ):
        start = text.index(f'    private void {method}(')
        end = text.index('\n    }', start)
        older = text[start:end]
        latest = once(older,
                      f'{row}.setEnabled(editable);\n        {row}.setAlpha(editable ? 1f : .55f);',
                      f'renderSiteSwitchEditability({row}, R.id.{label}, editable);')
        text = text[:start] + latest + text[end:]
    return once(text, '    private void configureColorCorrection() {', '''    private void renderSiteSwitchEditability(SwitchCompat row, int labelId, boolean editable) {
        row.setEnabled(editable);
        float alpha = editable ? 1f : .55f;
        row.setAlpha(alpha);
        mContent.findViewById(labelId).setAlpha(alpha);
    }

    private void configureColorCorrection() {''')


def transform(path: str, data: bytes) -> bytes:
    if OWNERS.get(path) != hashlib.sha256(data).hexdigest():
        raise ValueError(f'unexpected Shields alignment preimage: {path}')
    text = data.decode('utf-8')
    return (_layout(text) if path == LAYOUT else _java(text)).encode('utf-8')
