"""Local guard and evidence tests; no Chromium GN, CI or APK execution."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import raws_codec_trial as trial
import ci_official
import ci_restore_only


class TrialTest(unittest.TestCase):
    def effective(self, distinct=False):
        return (
            'proprietary_codecs = true\nffmpeg_branding = "Chrome"\n'
            'media_use_ffmpeg = true\nis_chrome_branded = false\n'
            'is_chrome_for_testing_branded = false\n'
            f'chrome_public_manifest_package = "{trial.APPLICATION_ID if distinct else "org.chromium.chrome"}"\n'
        ) + ''.join(name + ' = false\n' for name in (
            trial.BASELINE_OPTION_OVERRIDES + trial.DERIVED_BASELINE_OPTIONS))

    def test_exact_append_only_documented_flags_and_package(self):
        base = (trial.ROOT/'ci/args.gn').read_bytes()
        expected = base + b'\n# Test-only RawS codec comparison.\n' + trial.FLAGS
        self.assertEqual(trial.compose(base, False), expected)
        test_only = trial.compose(base, True)
        self.assertEqual(test_only, expected.replace(
            b'\n# Test-only', f'chrome_public_manifest_package = "{trial.APPLICATION_ID}"\n\n# Test-only'.encode(), 1))
        for drift in (base.replace(b'arm64', b'x64'), expected, base+b'\n'):
            with self.assertRaises(ValueError):
                trial.compose(drift, False)

    def test_resolved_settings_reject_wrong_missing_duplicate(self):
        for distinct in (False, True):
            value = self.effective(distinct)
            self.assertEqual(trial.check_media_args(value, distinct)['proprietary_codecs'], 'true')
            for invalid in (value.replace('proprietary_codecs = true', 'proprietary_codecs = false'),
                            value.replace('ffmpeg_branding = "Chrome"\n', ''),
                            value+'ffmpeg_branding = "Chrome"\n',
                            value.replace('is_chrome_branded = false', 'is_chrome_branded = true'),
                            value.replace('media_use_ffmpeg = true', 'media_use_ffmpeg = false'),
                            self.effective(not distinct)):
                with self.assertRaises(ValueError):
                    trial.check_media_args(invalid, distinct)

    def test_baseline_media_options_pinned_and_derived_settings_verified(self):
        expected = (
            'media_use_openh264', 'enable_hls_demuxer',
            'enable_hevc_parser_and_hw_decoder',
        )
        self.assertEqual(trial.BASELINE_OPTION_OVERRIDES, expected)
        for name in expected:
            self.assertIn(name.encode() + b' = false\n', trial.FLAGS)
        for name in trial.DERIVED_BASELINE_OPTIONS:
            self.assertNotIn(name.encode() + b' = false\n', trial.FLAGS)
        for name in expected + trial.DERIVED_BASELINE_OPTIONS:
            original = name + ' = false\n'
            with self.subTest(name=name):
                for drift in (self.effective().replace(original, name + ' = true\n'),
                              self.effective().replace(original, '')):
                    with self.assertRaisesRegex(ValueError, name):
                        trial.check_media_args(drift, False)

    def make_configs(self, ffmpeg):
        for brand, enabled in (('Chromium', 0), ('Chrome', 1)):
            p = ffmpeg/f'chromium/config/{brand}/android/arm64/config_components.h'
            p.parent.mkdir(parents=True)
            p.write_text(
                '#define CONFIG_MOV_DEMUXER 1\n' + ''.join(
                    f'#define CONFIG_{name} {enabled}\n' for name in (
                        'H264_DECODER', 'AAC_DECODER', 'H264_PARSER', 'AAC_PARSER')) +
                ''.join(f'#define CONFIG_{name} 0\n' for name in (
                    'HEVC_DECODER', 'HEVC_PARSER', 'HLS_DEMUXER')))

    def test_android_ffmpeg_configs_check_actual_profile_macros(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_configs(root)
            values = trial.check_ffmpeg_configs(root)
            self.assertEqual(values['Chrome']['features']['CONFIG_H264_DECODER'], '1')
            self.assertEqual(values['Chromium']['features']['CONFIG_H264_DECODER'], '0')
            path = root/values['Chrome']['path']
            path.write_text(path.read_text().replace('CONFIG_HEVC_PARSER 0', 'CONFIG_HEVC_PARSER 1'))
            with self.assertRaisesRegex(ValueError, 'CONFIG_HEVC_PARSER'):
                trial.check_ffmpeg_configs(root)

    def test_actual_environment_allowlist_and_no_existing_graph_reuse(self):
        env = trial.local_env(Path('/prepared/depot_tools'))
        self.assertTrue(env['PATH'].startswith('/prepared/depot_tools'))
        self.assertLessEqual(set(env), {'HOME', 'PATH', 'TMPDIR', 'LANG', 'LC_ALL', 'DEPOT_TOOLS_UPDATE'})
        with tempfile.TemporaryDirectory() as td:
            src, depot = Path(td)/'src', Path(td)/'depot_tools'
            src.mkdir()
            depot.mkdir()
            (depot/'gn').touch()
            destination = src/'out'
            destination.symlink_to(depot)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                trial.checked_paths(src, depot)

    def test_prepare_only_emits_separate_verified_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src, depot = root/'src', root/'depot_tools'
            self.make_configs(src/'third_party/ffmpeg')
            (src/'third_party/webrtc').mkdir()
            (src/'out/RawSandium').mkdir(parents=True)
            base = (trial.ROOT/'ci/args.gn').read_bytes()
            (src/'out/RawSandium/args.gn').write_bytes(base)
            depot.mkdir()
            (depot/'gn').touch()
            feature = Mock(identity=trial.FEATURE_SHA256, has_ui=True)
            lock = {'chromium': {'revision': trial.CHROMIUM},
                    'depot_tools': {'revision': 'pinned-test-depot'}}
            def git(path, *args):
                if args[0] in ('status', 'diff'):
                    return ''
                if path == trial.ROOT:
                    return trial.BASELINE_TREE if args[-1] == 'HEAD^{tree}' else trial.BASELINE
                return ('pinned-test-depot' if path == depot else
                        trial.WEBRTC if path.name == 'webrtc' else trial.FFMPEG)
            def verify(src, depot, out, env, artifacts, stage):
                self.assertEqual(out, artifacts)
                (out/f'gn-effective-{stage}.txt').write_text(self.effective(True))
                return {'effective_settings': {'is_official_build': 'true'}}
            out = src/trial.TRIAL_OUT
            with patch.object(trial, 'git', side_effect=git), patch.object(trial, 'lock', return_value=lock), patch.object(
                    ci_restore_only, 'active_feature', return_value=feature), patch.object(
                    ci_official, 'verify_official', side_effect=verify), patch.object(trial.subprocess, 'run') as gn:
                self.assertEqual(trial.prepare(src, depot, True), out)
                gn.assert_called_once()
                self.assertEqual(gn.call_args.args[0][1:], ['gen', trial.TRIAL_OUT, '--fail-on-unused-args'])
                self.assertEqual(feature.verify.call_count, 2)
                receipt = json.loads((out/'codec-trial-receipt.json').read_text())
                self.assertEqual(receipt['android_ffmpeg_configs']['Chrome']['features']['CONFIG_AAC_DECODER'], '1')
                self.assertFalse(receipt['apk_produced'])
                self.assertEqual(receipt['status'], 'gn_verified_not_compiled')
                self.assertEqual(receipt['trial_args_sha256'], trial.sha((out/'args.gn').read_bytes()))
                self.assertEqual((src/'out/RawSandium/args.gn').read_bytes(), base)
                with self.assertRaises(FileExistsError):
                    trial.prepare(src, depot, True)
                gn.assert_called_once()
                shutil.rmtree(out)
                gn.side_effect = RuntimeError('simulated generation failure')
                with self.assertRaises(RuntimeError):
                    trial.prepare(src, depot, True)
                self.assertFalse((out/'codec-trial-receipt.json').exists())


if __name__ == '__main__':
    unittest.main()
