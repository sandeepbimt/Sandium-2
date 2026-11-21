import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import raws_release_identity as identity


class ReleaseIdentityTest(unittest.TestCase):
    def setUp(self):
        self.pin = "a4" * 32
        self.badging = (
            f"package: name='{identity.APPLICATION_ID}' versionCode='812704200'\n"
            f"application-label:'{identity.DISPLAY_LABEL}'\n"
        )
        self.certs = f"Signer #1 certificate SHA-256 digest: {self.pin.upper()}\n"

    def test_passes_exact_project_identity(self):
        result = identity.verify_identity_reports(self.badging, self.certs, self.pin)
        self.assertTrue(result["apk_project_identity_verified"])
        self.assertEqual(result["apk_signer_cert_sha256"], self.pin)

    def test_rejects_old_package_even_with_matching_cert(self):
        old_badging = self.badging.replace(identity.APPLICATION_ID, "org.chromium.chrome")
        with self.assertRaisesRegex(ValueError, "application ID"):
            identity.verify_identity_reports(old_badging, self.certs, self.pin)

    def test_rejects_chromium_label(self):
        with self.assertRaisesRegex(ValueError, "application label"):
            identity.verify_identity_reports(self.badging.replace("Sandium", "Chromium"),
                                             self.certs, self.pin)

    def test_rejects_wrong_missing_and_extra_certificates(self):
        second = f"Signer #2 certificate SHA-256 digest: {'ce' * 32}\n"
        for certificates in ("", second, self.certs + second, self.certs * 2):
            with self.subTest(certificates=certificates), self.assertRaisesRegex(ValueError, "certificate"):
                identity.verify_identity_reports(self.badging, certificates, self.pin)

    def test_no_certificate_autodiscovery(self):
        for pin in (None, "", self.pin.upper(), "sha256:" + self.pin):
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                identity.verify_identity_reports(self.badging, self.certs, pin)

    def test_actual_signature_verification_invoked(self):
        with mock.patch.object(identity.subprocess, "check_output",
                               side_effect=(self.badging, self.certs)) as runner:
            identity.verify_release_identity("raws.apk", "aapt2", "apksigner", self.pin)
        self.assertEqual(runner.call_args_list[1].args[0],
                         ["apksigner", "verify", "--print-certs", "raws.apk"])

    def test_apksigner_failure_is_terminal(self):
        err = subprocess.CalledProcessError(1, ["apksigner"])
        with mock.patch.object(identity.subprocess, "check_output",
                               side_effect=(self.badging, err)):
            with self.assertRaises(subprocess.CalledProcessError):
                identity.verify_release_identity("raws.apk", "aapt2", "apksigner", self.pin)

    def test_gn_args_is_append_only_and_rejects_an_existing_assignment(self):
        baseline = 'target_cpu = "arm64"\n'
        args = identity.compose_gn_args(baseline)
        self.assertEqual(args, baseline +
                         f'chrome_public_manifest_package = "{identity.APPLICATION_ID}"\n')
        with self.assertRaisesRegex(ValueError, "already assigned"):
            identity.compose_gn_args(args)


    def test_missing_signing_secrets_never_invokes_sdk(self):
        with mock.patch.object(identity.subprocess, "check_output") as runner:
            with self.assertRaisesRegex(ValueError, "not provisioned"):
                identity.sign_release_locally("source.apk", "release.apk", "sdk", "project.jks",
                                              "raws", self.pin, expected_input_sha256=self.pin, env={})
        runner.assert_not_called()

    def test_signs_with_secret_only_in_signer_process_and_promotes_after_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output, key = (root / x for x in ("source.apk", "release.apk", "project.jks"))
            source.write_bytes(b"source")
            key.write_bytes(b"dummy")
            env = {"PATH": "/usr/bin", "RAWS_KEYSTORE_PASSWORD": "store-secret",
                   "RAWS_KEY_PASSWORD": "key-secret", "RBE_TOKEN": "unset"}
            calls = []

            def run(command, **opts):
                calls.append((command, opts["env"]))
                if command[1] == "dump":
                    return self.badging
                if command[1] == "sign":
                    Path(command[command.index("--out") + 1]).write_bytes(b"verified candidate")
                if command[1] == "verify":
                    self.assertFalse(output.exists())
                    return self.certs
                return ""

            with mock.patch.object(identity.subprocess, "check_output", side_effect=run):
                receipt = identity.sign_release_locally(source, output, root / "sdk", key,
                                                         "raws", self.pin, env=env,
                                                         expected_input_sha256=hashlib.sha256(b"source").hexdigest())
            self.assertTrue(receipt["apk_project_identity_verified"])
            self.assertEqual(output.read_bytes(), b"verified candidate")
            self.assertEqual(source.read_bytes(), b"source")
            for command, child_env in calls:
                self.assertNotIn("RBE_TOKEN", child_env)
                self.assertNotIn("store-secret", command)
                self.assertNotIn("key-secret", command)
                self.assertEqual("RAWS_KEY_PASSWORD" in child_env, command[1] == "sign")


    def test_mismatched_build_receipt_never_invokes_sdk(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output, key = (root / x for x in ("source.apk", "release.apk", "project.jks"))
            source.write_bytes(b"unexpected")
            key.write_bytes(b"dummy")
            env = {"RAWS_KEYSTORE_PASSWORD": "dummy", "RAWS_KEY_PASSWORD": "dummy"}
            with mock.patch.object(identity.subprocess, "check_output") as runner:
                with self.assertRaisesRegex(ValueError, "build receipt"):
                    identity.sign_release_locally(source, output, root / "sdk", key,
                                                  "raws", self.pin, env=env,
                                                  expected_input_sha256=self.pin)
            runner.assert_not_called()
            self.assertFalse(output.exists())


    def test_rejects_debuggable_variant(self):
        with self.assertRaisesRegex(ValueError, "debuggable"):
            identity.verify_identity_reports(self.badging + "application-debuggable\n",
                                             self.certs, self.pin)
