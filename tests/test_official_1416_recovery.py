"""Offline recovery guards; no CI cache is consumed by these fixtures."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('resume', ROOT/'.circleci/scripts/resume-official-1416.py')
resume = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resume)


class Recovery(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.flags = self.root/'brave-work/.sandium'
        self.flags.mkdir(parents=True)
        self.root_manifest = self.root/resume.MANIFEST_FILE
        self.inner_manifest = self.flags/'checkpoint-manifest.txt'
        self.inner_manifest.write_text(''.join(f'{k}={v}\n' for k, v in resume.EXPECTED.items()))
        self.data = {
            'schema_version': 2, 'format': 'independent-tar+zstd-shards',
            'workspace_root': 'brave-work', 'workers': 8, 'shards': [{}] * 8,
            'archive_bytes': resume.ARCHIVE_BYTES, 'source_bytes': resume.SOURCE_BYTES,
            'checkpoint_manifest': resume.EXPECTED.copy(),
            'checkpoint_manifest_sha256': resume.reference.digest(self.inner_manifest),
        }
        (self.flags/'build-stage-status.txt').write_text(
            'BUILD_EXIT_CODE=124\nBUILD_REASON=TIME_SLICE_COMPLETE\nBUILD_TIME_SLICE_EXPIRED=true\n'
            'BUILD_COMMAND_SUCCEEDED=false\nBUILD_SLICE_INCOMPLETE=true\nBUILD_HANDOFF_ALLOWED=true\n'
            'STAGE_BUILD_BUDGET_SECONDS=720\n')
        (self.flags/'apk-completion-status.txt').write_text('BUILD_FINISHED=false\n')

    def validate_fixture(self):
        encoded = json.dumps(self.data).encode()
        self.root_manifest.write_bytes(encoded)
        with patch.object(resume, 'MANIFEST_SHA', hashlib.sha256(encoded).hexdigest()):
            return resume.validate_checkpoint(self.root)

    def test_exact_provenance_and_unfinished_state(self):
        self.assertEqual(self.validate_fixture(), self.data)
        resume.validate_unfinished(self.root)
        self.root_manifest.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            resume.validate_checkpoint(self.root)

    def test_reject_other_stages_workflows_revisions_and_ready_apk(self):
        for key, bad in [('STAGE', '2'), ('WORKFLOW_ID', 'wrong'),
                         ('REFERENCE_SOURCE_REVISION', 'wrong'), ('REFERENCE_READY', 'true'),
                         ('APK_VALIDATED', 'true'), ('CHROMIUM_SHA', 'wrong')]:
            with self.subTest(key=key):
                self.data['checkpoint_manifest'] = {**resume.EXPECTED, key: bad}
                with self.assertRaisesRegex(ValueError, 'provenance'):
                    self.validate_fixture()

    def test_postrestore_checks_upstream_and_inner_manifest(self):
        with patch.object(resume.subprocess, 'run') as verify, patch.object(
                resume.reference, 'validate_gn_files') as gn:
            resume.postrestore(self.root, self.data)
            self.assertEqual(verify.call_args.args[0][-4:],
                             ['--handoff', '2', resume.SOURCE_WORKFLOW, resume.SOURCE_REVISION])
            gn.assert_called_once()
            self.inner_manifest.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'extracted checkpoint'):
                resume.postrestore(self.root, self.data)

    def test_retirement_leaves_compiled_objects_and_rejects_completed_seed(self):
        apk = self.root/resume.reference.APK_PATH
        apk.parent.mkdir(parents=True)
        apk.write_text('interrupted output')
        ninja = apk.parent.parent/'build.ninja'
        ninja.write_text('keep')
        marker = self.flags/'apk-completion-status.txt'
        marker.write_text('BUILD_FINISHED=true\n')
        with self.assertRaisesRegex(ValueError, 'unfinished'):
            resume.retire_outputs(self.root)
        self.assertTrue(apk.exists())
        marker.write_text('BUILD_FINISHED=false\n')
        resume.retire_outputs(self.root)
        self.assertFalse(apk.exists())
        self.assertFalse(marker.exists())
        self.assertEqual(ninja.read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
