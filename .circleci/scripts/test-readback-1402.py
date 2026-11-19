#!/usr/bin/env python3
"""Structural and fail-closed tests for the isolated Full #1402 readback."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("readback_1402", HERE / "readback-1402.py")
READBACK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(READBACK)


class Readback(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / "brave-workspace-checkpoint.manifest.json"
        metadata = READBACK.load("resume-official-1394.py").EXPECTED.copy()
        metadata.update(
            STAGE="2", WORKFLOW_ID=READBACK.WORKFLOW,
            REFERENCE_SOURCE_REVISION=READBACK.REVISION,
            APK_VALIDATED="true", REFERENCE_READY="true",
        )
        self.data = {
            "schema_version": 2, "format": "independent-tar+zstd-shards",
            "workers": 8, "shards": [{}] * 8, "archive_bytes": 35755833859,
            "checkpoint_manifest": metadata,
        }

    def write_fixture(self):
        self.manifest.write_text(json.dumps(self.data))
        return patch.object(READBACK, "MANIFEST_SHA", hashlib.sha256(self.manifest.read_bytes()).hexdigest())

    def test_observed_identities(self):
        self.assertEqual(READBACK.MANIFEST_SHA, "d6f47ee140ae7ec0ef36448f767e2fd90b1370da4e9bdae8673bd3fd93f47749")
        self.assertEqual(READBACK.APK_SHA, "db8a86a10c317a5c2fc806cd15ff01d2d23fe1f906c1648bf5e0c6a6e3cc09a9")
        self.assertEqual(READBACK.REVISION, "af15f567826041b83fb9295b12b3aa0d7c4b74ad")

    def test_valid_synthetic_manifest_and_tampered_digest(self):
        with self.write_fixture():
            READBACK.validate(self.root)
            self.manifest.write_text(self.manifest.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "checksum"):
                READBACK.validate(self.root)

    def test_wrong_stage_or_incomplete_apk_rejected_even_with_correct_digest(self):
        for key, value in [("STAGE", "1"), ("APK_VALIDATED", "false"), ("REFERENCE_READY", "false")]:
            with self.subTest(key=key):
                metadata = self.data["checkpoint_manifest"]
                original = metadata[key]
                metadata[key] = value
                with self.write_fixture(), self.assertRaisesRegex(ValueError, key):
                    READBACK.validate(self.root)
                metadata[key] = original

    def test_reject_preexisting_workspace_including_dangling_symlink(self):
        workspace = self.root / "brave-work"
        for symlink in [False, True]:
            with self.subTest(symlink=symlink):
                if symlink:
                    workspace.symlink_to(self.root / "missing")
                else:
                    workspace.mkdir()
                argv = ["readback", "preverify", "--root", str(self.root)]
                with self.write_fixture(), patch("sys.argv", argv), self.assertRaisesRegex(ValueError, "Fresh destination"):
                    READBACK.main()
                if symlink:
                    workspace.unlink()
                else:
                    workspace.rmdir()

    def test_config_only_manual_exact_readback_and_evidence(self):
        cfg = yaml.safe_load((HERE.parent / "config.yml").read_text())
        self.assertEqual(cfg["parameters"], {"run_readback": {"type": "boolean", "default": False}})
        self.assertEqual(list(cfg["jobs"]), ["verify-1402-archive"])
        workflow = cfg["workflows"]["verify-completed-Full-1402"]
        self.assertEqual(workflow["when"], "<< pipeline.parameters.run_readback >>")
        self.assertEqual(workflow["jobs"], [{"verify-1402-archive": {"filters": {"branches": {"only": "verify/1402-archive"}}}}])
        steps = cfg["jobs"]["verify-1402-archive"]["steps"]
        self.assertEqual([step if isinstance(step, str) else next(iter(step)) for step in steps],
                         ["checkout", "restore_cache", "run", "run", "run", "store_artifacts"])
        self.assertEqual(steps[1]["restore_cache"]["keys"], [
            "sandium-official-handoff-v1-fix/1394-official-lint-07214cac-daf8-47f1-a9dd-b48d229e934f-stage-2"
        ])
        self.assertEqual(steps[-1]["store_artifacts"], {"path": "readback-evidence"})


if __name__ == "__main__":
    unittest.main()
