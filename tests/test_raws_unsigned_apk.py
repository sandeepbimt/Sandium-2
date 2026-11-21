import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import ci_compile
import ci_sign_raws_test as ci
import raws_codec_ci as codec
import raws_release_identity as identity
import raws_unsigned_apk as pack


class UnsignedPackagingTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.apk = self.root / 'input.apk'

    def make_zip(self, path=None, extra=(), arch='arm64-v8a'):
        path = path or self.apk
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('AndroidManifest.xml', b'manifest')
            z.writestr('lib/' + arch + '/libchrome.so', b'lib')
            for name in extra:
                z.writestr(name, b'x')
        return path

    def test_plain_zip_only_and_rejects_signed_inputs(self):
        self.make_zip()
        self.assertEqual(['arm64-v8a'], pack.verify_zip(self.apk, unsigned=True))
        self.make_zip(extra=['META-INF/CERT.SF'])
        with self.assertRaisesRegex(ValueError, 'v1 signature'):
            pack.verify_zip(self.apk, unsigned=True)
        self.make_zip()
        raw = self.apk.read_bytes()
        eocd = raw.rindex(b'PK\x05\x06')
        cd = struct.unpack_from('<I', raw, eocd + 16)[0]
        block = b'not a real signature' + b'APK Sig Block 42'
        raw = bytearray(raw[:cd] + block + raw[cd:])
        struct.pack_into('<I', raw, eocd + len(block) + 16, cd + len(block))
        self.apk.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'signing block'):
            pack.verify_zip(self.apk, unsigned=True)
        Path(str(self.apk) + '.idsig').touch()
        with self.assertRaisesRegex(ValueError, 'v4 signature'):
            pack.verify_zip(self.apk, unsigned=True)

    def test_abi_duplicates_and_bad_zip_fail(self):
        self.make_zip(arch='x86_64')
        with self.assertRaisesRegex(ValueError, 'only arm64'):
            pack.verify_zip(self.apk, unsigned=True)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            self.make_zip(extra=['AndroidManifest.xml'])
        with self.assertRaisesRegex(ValueError, 'ZIP structure'):
            pack.verify_zip(self.apk, unsigned=False)
        self.apk.write_bytes(b'invalid')
        with self.assertRaises(zipfile.BadZipFile):
            pack.verify_zip(self.apk, unsigned=True)

    def test_alignment_and_exact_gn_graph(self):
        apk = self.make_zip()
        with patch.object(pack.subprocess, 'run') as run:
            pack.verify_aligned(apk, self.root/'zipalign', {})
            self.assertEqual(run.call_args.args[0][1:5], ['-c', '-P', '16', '4'])
        args = '--output-apk=apks/ChromePublic.apk\n--resource-apk=ChromePublic.ap_'
        ins = '//third_party/android_build_tools/signflinger/signflinger.jar'
        outputs = '//out/RawSandium/apks/ChromePublic.apk'
        for candidate_args, candidate_ins, candidate_out in [
                (args + '\n--key-path\nfoo', ins, outputs),
                (args, ins + '\n//foo/debug.keystore', outputs),
                (args, ins, outputs + '\n' + outputs + '.idsig')]:
            with patch.object(pack.subprocess, 'check_output',
                              side_effect=[candidate_args, candidate_ins, candidate_out]):
                with self.assertRaisesRegex(ValueError, 'did not omit'):
                    pack.verify_graph(self.root, 'gn', self.root/'out', {})
        with patch.object(pack.subprocess, 'check_output', side_effect=[args, ins, outputs]):
            self.assertTrue(pack.verify_graph(self.root, 'gn', self.root/'out', {}))

    def test_unsigned_flags_are_bound_into_codec_arguments(self):
        (self.root / 'ci').mkdir()
        shutil.copyfile(Path(__file__).resolve().parents[1] / 'ci/args.gn', self.root / 'ci/args.gn')
        with patch.dict(os.environ, {}, clear=True):
            normal = codec.expected_args(self.root)
            self.assertNotIn(pack.ARG.encode(), normal)
        with patch.dict(os.environ, {'RAWS_UNSIGNED_TEST_APK':'true'}, clear=True):
            self.assertEqual(codec.expected_args(self.root), normal + b'raws_unsigned_test_apk = true\n')
            with self.assertRaises(ValueError):
                pack.append_arg(pack.append_arg('target_cpu = "arm64"\n'))
        with patch.dict(os.environ, {'RAWS_UNSIGNED_TEST_APK':'yes'}, clear=True):
            with self.assertRaises(ValueError):
                pack.mode()

    def test_exact_unsigned_handoff_requires_both_ends_receipt(self):
        self.make_zip()
        manifest = self.root / 'raws-adblock/production-restore-recipe.json'
        manifest.parent.mkdir()
        manifest.write_text('{}')
        run = ('f'*40, '00000000-0000-4000-8000-000000000001')
        state = dict.fromkeys((*ci.EVIDENCE, *pack.SIGN_FIELDS), True)
        state.update(stage=1, status='done', apk_package=ci.APPLICATION_ID,
                     apk_abis=['arm64-v8a'], feature_recipe_sha256=ci.sha256(manifest),
                     apk_sha256=ci.sha256(self.apk), apk_signature_verified=False,
                     android_java_body_gate={'output':pack.JAVA_BODY_JAR, 'sha256':'b'*64, 'passed':True},
                     raws_engine_smoke={'cases':list(range(13))+['incident1471-player-rules']})
        with patch.dict(os.environ, {'RAWS_UNSIGNED_TEST_APK':'true'}, clear=True), \
                patch.object(ci, 'run_identity', return_value=run):
            with self.assertRaisesRegex(ValueError, 'Unverified'):
                ci.stage_private_input(self.root, {**state, 'apk_signature_verified': True}, self.apk)
            with self.assertRaisesRegex(ValueError, 'Java body compiler evidence'):
                ci.stage_private_input(self.root, {**state, 'android_java_body_gate': {}}, self.apk)
            ci.stage_private_input(self.root, state, self.apk)
            _, proof = ci.input_receipt(self.root, self.root/ci.HANDOFF)
            self.assertEqual(proof['unsigned_packaging'], dict.fromkeys(pack.SIGN_FIELDS, True))
            self.assertEqual(proof['input_sha256'], state['apk_sha256'])
            self.assertEqual(proof['android_java_body_gate'], state['android_java_body_gate'])
            self.assertFalse((self.root/'artifacts').exists())
        with patch.dict(os.environ, {}, clear=True), patch.object(ci, 'run_identity', return_value=run):
            with self.assertRaisesRegex(ValueError, 'exact candidate'):
                ci.input_receipt(self.root, self.root/ci.HANDOFF)

    def test_isolated_signer_calls_sdk_sign_once_and_only_then_promotes(self):
        self.make_zip()
        key = self.root/'fake-key'
        key.touch()  # empty fixture only; no real key or signing material
        output = self.root/'published.apk'
        sha = ci.sha256(self.apk)
        seen = []
        def command(cmd, **kwargs):
            self.assertFalse(output.exists())
            seen.append((Path(cmd[0]).name, cmd[1], tuple(kwargs['env'])))
            if cmd[1] == 'sign':
                self.assertIn('--v4-signing-enabled', cmd)
                self.make_zip(Path(cmd[cmd.index('--out')+1]), extra=['META-INF/FAKE.SF'])
            if cmd[1] == 'dump':
                return "package: name='io.github.sandeepbimt.raws'\napplication-label:'Sandium'\n"
            if cmd[1] == 'verify':
                return 'Signer #1 certificate SHA-256 digest: ' + 'a'*64 + '\n'
            return ''
        env = {'PATH':'/sdk','RAWS_KEYSTORE_PASSWORD':'fixture','RAWS_KEY_PASSWORD':'fixture'}
        with patch.object(identity.subprocess, 'check_output', side_effect=command):
            proof = identity.sign_release_locally(self.apk, output, self.root, key, 'fake',
                                                   'a'*64, expected_input_sha256=sha,
                                                   env=env, unsigned_input=True)
        self.assertEqual([item for item in seen if item[1]=='sign'],
                         [('apksigner','sign',tuple(env))])
        self.assertTrue(all(item[2] == ('PATH',) for item in seen if item[1] != 'sign'))
        self.assertEqual(proof['apk_input_sha256'], sha)
        self.assertEqual(proof['apk_sha256'], ci.sha256(output))
        self.assertEqual(proof['apk_abis'], ['arm64-v8a'])
        self.assertIs(proof['apk_zipalign_16k_verified'], True)
        self.assertIs(proof['apk_signature_verified'], True)

    def test_java_body_uses_exact_action_same_output_and_remaining_deadline(self):
        out = self.root/'out/RawSandium'
        target = 'obj/chrome/android/chrome_java.javac.jar'
        jar = out/target
        jar.parent.mkdir(parents=True)
        jar.write_bytes(b'java body fixture output')
        gn_reply = '//out/RawSandium/' + target + '\n//out/RawSandium/obj/other.jar\n'
        with patch.object(ci_compile.subprocess, 'check_output', return_value=gn_reply), \
                patch.object(ci_compile.time, 'monotonic', return_value=100), \
                patch.object(ci_compile, 'run_logged', return_value=subprocess.CompletedProcess([],0)) as run:
            p = ci_compile.run_java_body_gate(self.root, 'gn', out, {}, self.root, 1, 240)
            self.assertIs(p['passed'], True)
            self.assertEqual(p['sha256'], hashlib.sha256(jar.read_bytes()).hexdigest())
            cmd = run.call_args.args[0]
            self.assertEqual(cmd[3], '140s')
            self.assertIn('-strict_remote', cmd)
            self.assertEqual(cmd[-1], target)
        with patch.object(ci_compile.subprocess, 'check_output',
                          return_value=gn_reply.replace('.javac.jar','.turbine.jar')):
            with self.assertRaisesRegex(ValueError, 'exact Android'):
                ci_compile.java_body_output(self.root,'gn',out,{})

    def test_exact_pinned_gn_and_packer_fixture_if_supplied(self):
        fixture = os.environ.get('RAWS_PINNED_PACKAGING_FIXTURE')
        if not fixture:
            self.skipTest('exact Chromium source fixture not supplied')
        for name in pack.PINS:
            f = self.root/name
            f.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(fixture)/name, f)
        overlay=pack.PackagingOverlay(self.root)
        overlay.apply()
        overlay.verify()
        rules = (self.root/'build/config/android/rules.gni').read_text()
        self.assertIn('raws_unsigned_test_apk = false', rules)
        self.assertIn('_template_name == "chrome_public_apk"', rules)
        internal = (self.root/'build/config/android/internal_rules.gni').read_text()
        self.assertIn('|| !invoker.raws_unsigned', internal)
        self.assertEqual(internal.count('is_robolectric_apk'), 5)
        overlay.restore()
        self.assertEqual(overlay.applied, [])
        for file, (baseline, _) in overlay.files.items():
            self.assertEqual(file.read_bytes(), baseline)


if __name__ == '__main__':
    unittest.main()
