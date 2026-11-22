"""Deterministic local proof tests; no CI, signing keys, compiler or APK streams."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import ci_restore_only
import ci_sign_raws_test as signer
import raws_codec_ci as codec
import raws_codec_trial as profile
import test_raws_signing_handoff as handoff
import test_raws_codec_trial as local_trial


class CodecCIProofTest(unittest.TestCase):
    def setUp(self):
        handoff.SigningHandoffTest.setUp(self)
        self.repo = Path(__file__).resolve().parents[1]
        self.out = self.root/'test-out'
        self.out.mkdir()
        ci = self.root/'ci'
        ci.mkdir()
        baseline = (self.repo/'ci/args.gn').read_bytes()
        (ci/'args.gn').write_bytes(baseline)
        (self.out/'args.gn').write_bytes(profile.compose(baseline, True))
        self.header = self.out/'gen/media/media_buildflags.h'
        self.header.parent.mkdir(parents=True)
        self.header.write_text(''.join(f'#define BUILDFLAG_INTERNAL_{k}() ({v})\n'
                                       for k, v in codec.BUILD_FLAGS.items()))
        ffmpeg = self.root/'ffmpeg'
        local_trial.TrialTest.make_configs(None, ffmpeg)
        self.proof = codec.compile_proof(self.root, self.out, profile.media_settings(True),
                                         profile.check_ffmpeg_configs(ffmpeg),
                                         {'cases': list(codec.NATIVE_SMOKE_CASES)})
        self.state['raws_engine_smoke']['cases'] = list(codec.NATIVE_SMOKE_CASES)
        self.manifest = self.root/'raws-adblock/production-restore-recipe.json'

    def stage(self):
        return handoff.SigningHandoffTest.stage(self)

    def test_generated_buildflag_header_rejects_missing_or_false(self):
        self.header.write_text(self.header.read_text().replace('USE_PROPRIETARY_CODECS() (1)',
                                                               'USE_PROPRIETARY_CODECS() (0)'))
        with self.assertRaisesRegex(ValueError, 'USE_PROPRIETARY_CODECS'):
            codec.read_generated_header(self.out)
        self.header.unlink()
        with self.assertRaisesRegex(ValueError, 'No generated media'):
            codec.read_generated_header(self.out)

    def test_mode_must_be_selected_at_both_ends(self):
        self.state['codec_trial'] = self.proof
        with patch.object(codec, 'mode', return_value=False):
            with self.assertRaisesRegex(ValueError, 'ordinary test signing'):
                self.stage()
        with patch.object(codec, 'mode', return_value=True):
            source = self.stage()
            with patch.object(signer, 'run_identity', return_value=self.run), \
                    patch.object(codec, 'verify_checkout'):
                apk, proof = signer.input_receipt(self.root, source)
                self.assertEqual(proof['codec_trial'], self.proof)
                self.assertEqual(proof['input_sha256'], signer.sha256(apk))
                with patch.object(codec, 'mode', return_value=False):
                    with self.assertRaisesRegex(ValueError, 'exact candidate'):
                        signer.input_receipt(self.root, source)
                mutated = copy.deepcopy(proof)
                mutated['codec_trial']['generated_media_buildflags']['ENABLE_HLS_DEMUXER'] = 1
                (source/'receipt.json').write_text(json.dumps(mutated))
                with self.assertRaisesRegex(ValueError, 'inconsistent private codec proof'):
                    signer.input_receipt(self.root, source)

    def test_combined_native_player_incident_proof_cannot_be_replaced(self):
        self.state['codec_trial'] = self.proof
        with patch.object(codec, 'mode', return_value=True):
            self.state['raws_engine_smoke']['cases'][0] = 'different-case'
            with self.assertRaisesRegex(ValueError, 'actual native smoke receipt'):
                self.stage()
        del self.proof['native_smoke_cases'][-1]
        with self.assertRaisesRegex(ValueError, 'inconsistent private codec proof'):
            codec.validate_proof(self.root, self.proof)

    def test_codec_artifact_has_unique_name_and_test_only_receipt(self):
        self.state['codec_trial'] = self.proof
        dest = self.root/'artifact'
        with patch.object(codec, 'mode', return_value=True):
            source = self.stage()
            def pretend_sign(apk, path, *args, **kwargs):
                self.assertEqual(path.name, codec.TRIAL_APK)
                self.assertEqual(kwargs['expected_input_sha256'], signer.sha256(apk))
                path.write_bytes(b'synthetic signed apk')
                return {'apk_sha256': signer.sha256(path)}
            with patch.object(signer, 'run_identity', return_value=self.run), \
                    patch.object(codec, 'verify_checkout'), \
                    patch.object(signer, 'sign_release_locally', side_effect=pretend_sign), \
                    patch.dict(signer.os.environ, {'RAWS_TEST_SIGNER_PIN_SHA256': 'a'*64,
                                                  'RAWS_TEST_KEYSTORE_B64': 'YQ=='}, clear=True):
                signer.sign(self.root, source, self.root/'sdk', dest)
        receipt = json.loads((dest/'signing-receipt.json').read_text())
        self.assertIs(receipt['distribution_ready'], False)
        self.assertEqual(receipt['codec_trial'], self.proof)
        self.assertEqual(receipt['apk_sha256'], signer.sha256(dest/codec.TRIAL_APK))
        self.assertFalse((dest/signer.APK_NAME).exists())

    def test_codec_profile_requires_isolated_signed_route(self):
        with patch.object(codec, 'mode', return_value=True), patch.object(
                ci_restore_only, 'distinct_test_mode', return_value=False):
            with self.assertRaisesRegex(ValueError, 'isolated signed'):
                ci_restore_only.gate()

    def checkout_git(self, *, parent=None, source_parent=None, control_tree=None,
                     ci_tree=None, changes=None, dirty='', mode='100644'):
        def commit(path, *args):
            if args[0] == 'show':
                return (codec.BASELINE if parent is None else parent) if args[-1] == 'HEAD' else (
                    codec.FROZEN_SOURCE_BASELINE if source_parent is None else source_parent)
            if args[0] == 'rev-parse':
                requested = args[-1]
                if requested.endswith(':.circleci'):
                    return codec.FROZEN_CI_TREE if ci_tree is None else ci_tree
                if requested == codec.BASELINE + '^{tree}':
                    return codec.BASELINE_TREE if control_tree is None else control_tree
                self.assertEqual(requested, codec.FROZEN_SOURCE_BASELINE + '^{tree}')
                return codec.FROZEN_SOURCE_TREE
            if args[0] == 'ls-tree':
                return mode + ' blob ' + 'a'*40 + '\t' + args[-1]
            if '-z' in args:
                return '\0'.join(sorted(codec.SCOPED_FILES)) + '\0' if changes is None else changes
            self.assertEqual(args, ('diff', 'HEAD', '--name-only'))
            return dirty
        return commit

    def prepare_checkout_manifest(self):
        self.manifest.write_bytes((self.repo/self.manifest.relative_to(self.root)).read_bytes())

    def test_exact_control_parents_paths_and_manifest(self):
        self.prepare_checkout_manifest()
        with patch.object(codec, 'git', side_effect=self.checkout_git()):
            codec.verify_checkout(self.root)
        self.manifest.write_bytes(b'changed')
        with patch.object(codec, 'git', side_effect=self.checkout_git()):
            with self.assertRaisesRegex(ValueError, 'browser overlay'):
                codec.verify_checkout(self.root)

    def test_unchanged_ci_contract_required(self):
        self.prepare_checkout_manifest()
        with patch.object(codec, 'git', side_effect=self.checkout_git(ci_tree='a'*40)):
            with self.assertRaisesRegex(ValueError, 'unchanged #1495 CI'):
                codec.verify_checkout(self.root)

    def test_scope_rejects_extra_missing_and_malformed_control_files(self):
        self.prepare_checkout_manifest()
        allowed = '\0'.join(sorted(codec.SCOPED_FILES)) + '\0'
        for change in (allowed + 'ci/args.gn\0', allowed[:-1], 'tools/raws_codec_ci.py\0',
                       allowed.replace('tools/raws_codec_trial.py', 'tools/"raws_codec_trial.py"'),
                       allowed.replace('tools/raws_codec_trial.py', 'tools/raws_codec_trial.py\n'),
                       allowed.replace('tools/raws_codec_trial.py', 'tools/raws_codec_ci.py')):
            with self.subTest(change=change), patch.object(
                    codec, 'git', side_effect=self.checkout_git(changes=change)):
                with self.assertRaisesRegex(ValueError, 'allowed combined RawS'):
                    codec.verify_checkout(self.root)
        with patch.object(codec, 'git', side_effect=self.checkout_git(mode='120000')):
            with self.assertRaisesRegex(ValueError, 'invalid control file'):
                codec.verify_checkout(self.root)

    def test_parent_trees_pins_and_tracked_dirty_checkout_are_rejected(self):
        self.prepare_checkout_manifest()
        for overrides in ({'parent':'a'*40}, {'source_parent':'b'*40}, {'control_tree':'c'*40},
                          {'dirty':'tools/raws_codec_ci.py'}):
            with self.subTest(overrides=overrides), patch.object(
                    codec, 'git', side_effect=self.checkout_git(**overrides)):
                with self.assertRaises(ValueError):
                    codec.verify_checkout(self.root)
        with patch.object(codec, 'BASELINE', 'malformed'):
            with self.assertRaisesRegex(ValueError, 'Malformed'):
                codec.verify_checkout(self.root)

    def test_failed_predecessor_cannot_be_used_as_codec_child(self):
        self.prepare_checkout_manifest()
        with patch.object(codec, "git", side_effect=self.checkout_git(
                parent=codec.FROZEN_SOURCE_BASELINE)):
            with self.assertRaisesRegex(ValueError, "exact RawS #1508"):
                codec.verify_checkout(self.root)
