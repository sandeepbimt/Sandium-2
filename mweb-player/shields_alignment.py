"""Align the three native site switch labels with their Shields action rows."""

import hashlib
import re

LAYOUT = 'chrome/android/java/res/layout/raws_global_shield_sheet.xml'
OWNERS = {
    LAYOUT: '2a3b9496d5e352cfc7413e72bce77b8266cced0c1fe0179e2767d0c6fd333ef7',
}
SITE_SWITCHES = ('raws_shields_ads', 'raws_shields_dark_pages', 'raws_shields_block_cookies')

OLD_ATTRIBUTES = (
    'android:paddingHorizontal="16dp" android:paddingVertical="4dp" '
    'android:gravity="center_vertical"'
)
NEW_ATTRIBUTES = (
    'android:paddingStart="16dp" android:paddingEnd="16dp" android:paddingVertical="4dp" '
    'android:gravity="start|center_vertical" android:textAlignment="viewStart"'
)


def transform(path: str, data: bytes) -> bytes:
    if OWNERS.get(path) != hashlib.sha256(data).hexdigest():
        raise ValueError(f'unexpected Shields alignment preimage: {path}')
    text = data.decode('utf-8')
    for switch in SITE_SWITCHES:
        pattern = (
            r'<com\.google\.android\.material\.materialswitch\.MaterialSwitch\b'
            r'[^<>]* android:id="@\+id/' + re.escape(switch) + r'" />'
        )
        matches = list(re.finditer(pattern, text))
        if len(matches) != 1 or matches[0][0].count(OLD_ATTRIBUTES) != 1:
            raise ValueError(f'missing or ambiguous Shields switch: {switch}')
        row = matches[0]
        text = text[:row.start()] + row[0].replace(OLD_ATTRIBUTES, NEW_ATTRIBUTES, 1) + text[row.end():]
    return text.encode('utf-8')
