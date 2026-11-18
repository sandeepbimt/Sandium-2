import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from ci_official import validate_settings, validate_flags
from ci_compile import fingerprint

SETTINGS = '''is_official_build = true
is_debug = false
is_component_build = false
target_os = "android"
target_cpu = "arm64"
use_thin_lto = true
use_remoteexec = true
use_siso = true
use_reclient = false
chrome_pgo_phase = 2
'''

class OfficialTests(unittest.TestCase):
    def test_optimization_cannot_silently_disable(self):
        self.assertEqual(validate_settings(SETTINGS)[1], 'pgo')
        for old, new in [('is_official_build = true', 'is_official_build = false'),
                         ('use_thin_lto = true', 'use_thin_lto = false'),
                         ('chrome_pgo_phase = 2', 'chrome_pgo_phase = 0'),
                         ('use_remoteexec = true', 'use_remoteexec = false')]:
            with self.assertRaises(ValueError):
                validate_settings(SETTINGS.replace(old, new))
        self.assertEqual(validate_settings(SETTINGS.replace('chrome_pgo_phase = 2',
            'chrome_pgo_phase = 0\nclang_use_default_sample_profile = true'))[1], 'afdo')

    def test_graph_profile_is_exact_present_and_hashed(self):
        with tempfile.TemporaryDirectory() as folder:
            src = Path(folder); out = src/'out/RawSandium'; out.mkdir(parents=True)
            profile = src/'chrome/android/orderfiles/arm64/pgo_profile.arm64.profdata'
            profile.parent.mkdir(parents=True); profile.write_bytes(b'pinned-profile')
            flags = ['-flto=thin', '-fprofile-use=../../chrome/android/orderfiles/arm64/pgo_profile.arm64.profdata']
            receipt = validate_flags({'//base:base': {'cflags': flags}}, out, src, 'pgo')
            self.assertEqual(receipt['bytes'], 14)
            for bad in (flags[1:], flags[:1], flags + [flags[1]], ['-flto=thin', '-fprofile-use=/tmp/other']):
                with self.assertRaises(ValueError):validate_flags({'cflags': bad}, out, src, 'pgo')
            profile.unlink()
            with self.assertRaises(ValueError):validate_flags({'cflags': flags}, out, src, 'pgo')

    def test_new_namespace_cannot_restore_156(self):
        self.assertNotEqual(fingerprint(), '27d987b96e7aa1f6e33b189d06f27345d62695aeefbae39dd6adeca421eed945')
        self.assertEqual((ROOT/'ci/cache-identity.txt').read_text().strip(), fingerprint())
        lock = json.loads((ROOT/'upstream.lock.json').read_text())
        self.assertEqual(lock['gclient_custom_vars'], {'checkout_pgo_profiles': True})
        self.assertEqual(lock['chromium']['revision'], '52bdd21723d5db0c9ab11716d38feac74828cf84')

    def test_config_regenerates_without_drift(self):
        import yaml
        from generate_full_config import generate
        from generate_final_archive_config import generate_archive
        self.assertEqual(yaml.safe_load((ROOT/'.circleci/config.yml').read_text()), generate())
        self.assertEqual(yaml.safe_load((ROOT/'.circleci/final-archive.yml').read_text()), generate_archive())
