#!/usr/bin/env python3
"""Tests for source-only output provenance checks."""
import tempfile
import unittest
from pathlib import Path
from sandium_pinned_source_checkpoint import validate_source_only_outputs

class SourceOnlyOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.out = self.root / "brave-work/src/out/android_Release_arm64"
        self.out.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_bundled_dependency_apks_are_not_mistaken_for_sandium_builds(self):
        bundled = self.root / "brave-work/src/third_party/testdata/sample.apk"
        bundled.parent.mkdir(parents=True)
        bundled.write_bytes(b"fixture")
        result = validate_source_only_outputs(self.root)
        self.assertEqual(result["bundled_source_apks"], 1)
        self.assertEqual(result["sandium_apk_outputs"], 0)

    def test_actual_arm64_release_apk_output_is_rejected(self):
        apk = self.out / "apks/BraveMonoarm64.apk"
        apk.parent.mkdir()
        apk.write_bytes(b"built apk")
        with self.assertRaisesRegex(ValueError, "package Sandium APKs"):
            validate_source_only_outputs(self.root)

    def test_compiled_object_file_is_rejected(self):
        obj = self.out / "obj/chrome/browser/browser.o"
        obj.parent.mkdir(parents=True)
        obj.write_bytes(b"object")
        with self.assertRaisesRegex(ValueError, "compile object files"):
            validate_source_only_outputs(self.root)

if __name__ == "__main__":
    unittest.main(verbosity=2)
