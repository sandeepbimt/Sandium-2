#!/usr/bin/env python3
"""Pinned-source replay/idempotence checks. Not Android/device validation."""
import argparse
import hashlib
import difflib
import importlib.util
from pathlib import Path
import shutil
import tempfile

spec = importlib.util.spec_from_file_location('links', Path(__file__).with_name('apply-sandium-ui-links.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
p = argparse.ArgumentParser()
p.add_argument('--core', type=Path, required=True)
p.add_argument('--src', type=Path, required=True)
a = p.parse_args()
with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    for rel in m.PATHS:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(a.core / rel, dest)
    m.apply(root)
    first = [(root / rel).read_text() for rel in m.PATHS]
    m.apply(root)
    assert first == [(root / rel).read_text() for rel in m.PATHS]
    settings, webrtc, background, privacy, filters, tutorial, notification = first
    assert settings.index('boolean prepared = super.onPreparePanel') < settings.index('if (menu != null) removeSandiumSupportItems(menu)')
    assert 'menu_id_general_help' in settings and 'menu_id_targeted_help' in settings
    assert 'mLearnMore.setVisibility(View.GONE)' in webrtc
    assert 'Uri.parse(FALLBACK_SUPPORT_URL)' not in webrtc
    assert 'mGroup.setOnCheckedChangeListener(this)' in webrtc
    assert 'mSettingRadioButton.setChecked(true)' in webrtc
    assert 'if (mLearnMorePreference != null) { // Sandium' in background
    assert 'mBlockCrosssiteCookiesLearnMore.setSummary(learnMoreDesc)' in privacy
    assert 'BLOCK_ALL_COOKIES_LEARN_MORE_LINK);' not in privacy
    assert 'tvSummary.setMovementMethod(null)' in filters
    assert 'getActivity(), BRAVE_ADBLOCK_FILTER_SYNTAX_PAGE' not in filters
    assert 'initFilterListAndroidHandler();' in filters
    assert 'openNewOrSelectExistingTab(NTP_TUTORIAL_PAGE)' not in tutorial
    assert 'mNotificationManager.notify(' not in notification
    connection = root / m.CONNECTION
    connection.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(a.src / m.CONNECTION, connection)
    live_input_sha256 = hashlib.sha256(connection.read_bytes()).hexdigest()
    m.apply_chromium(root)
    c = connection.read_text()
    m.apply_chromium(root)
    assert c == connection.read_text()
    assert 'mDescriptionLayout.addView(mMoreInfoLink)' not in c
    assert 'mCertificateLayout.addView(mCertificateViewerTextView)' in c
    assert 'resetCertDecisions(' in c
    assert 'private void addMoreInfoLink(String unusedLinkText)' in c
    assert '@CalledByNative' in c
    for dead in ('HELP_URL', 'mMoreInfoLink', 'mLinkUrl', 'showConnectionSecurityInfo', 'import android.content.Intent;', 'import android.provider.Browser;', 'import org.chromium.base.Log;'):
        assert dead not in c, dead
    # Upgrade the failed #1179 generated no-op as well as pristine pinned source.
    # CI invokes this test AFTER applying the overlay to --src. Historical
    # migration/drift cases must use hermetic pristine input, not that live tree.
    fixture = Path(__file__).resolve().parents[2] / 'tests/fixtures/ui-links/ConnectionInfoView.java'
    original = fixture.read_text()
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == '5a30895d6511c7cb3a2bf02d3e1d03d15541dfb63fdae91e583760f356147770'
    connection.write_text(original)
    m.apply_chromium(root)
    expected = connection.read_text()
    if expected != c:
        print('SANDIUM_UI_LINKS_MISMATCH live_input_sha256=' + live_input_sha256 + ' expected_sha256=' + hashlib.sha256(expected.encode()).hexdigest()
              + ' actual_sha256=' + hashlib.sha256(c.encode()).hexdigest(), flush=True)
        print(''.join(difflib.unified_diff(expected.splitlines(keepends=True),
              c.splitlines(keepends=True), fromfile='pinned-transformed',
              tofile='actual-transformed')), flush=True)
        raise AssertionError('pristine and actual-tree outputs differ')
    begin = original.index('    private void addMoreInfoLink(String linkText) {')
    finish = original.index('\n    }', begin) + len('\n    }')
    previous = """    private void addMoreInfoLink(String linkText) {
        // Sandium: retain local security information, omit external support link.
    }"""
    connection.write_text(original[:begin] + previous + original[finish:])
    m.apply_chromium(root)
    assert connection.read_text() == c
    connection.write_text(original.replace('        // TODO(crbug.com/40129299):', '        // changed launcher:'))
    try:
        m.apply_chromium(root)
        raise AssertionError('launcher drift not rejected')
    except RuntimeError:
        pass
    connection.write_text(c)
    # Each whole-method suppression must reject an unreviewed body, not merely
    # locate a signature and overwrite newly added security/product behavior.
    for rel in (m.PATHS[5], m.PATHS[6], m.CONNECTION):
        target = root / rel
        saved = target.read_text()
        target.write_text(saved.replace('// Sandium:', '// Unreviewed change:', 1))
        try:
            (m.apply_chromium if rel == m.CONNECTION else m.apply)(root)
            raise AssertionError('whole-method drift not rejected: ' + rel)
        except RuntimeError:
            pass
        target.write_text(saved)
    # Reject silently applying against a changed target.
    target = root / m.PATHS[1]
    target.write_text(target.read_text().replace('mLearnMore.setVisibility(View.GONE);', 'changed();'))
    try:
        m.apply(root)
        raise AssertionError('drift not rejected')
    except RuntimeError:
        pass
print('SANDIUM_UI_LINKS_TEST=PASS replay idempotence drift retained_controls')
