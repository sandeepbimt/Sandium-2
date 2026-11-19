"""Execute the actual serialized gate and assert publication/handoff ordering."""
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
NAME = 'Skip large handoff after verified APK publication'
VALID = dict.fromkeys((
    'BUILD_FINISHED', 'APK_ARCHIVE_VALID', 'APK_SIGNATURE_VALID',
    'APK_PACKAGE_ID_VALID', 'APK_BRANDING_VALID', 'APK_REMOVALS_VALID',
), 'true')
TIMEOUT = {
    'BUILD_REASON': 'TIME_SLICE_COMPLETE',
    'BUILD_TIME_SLICE_EXPIRED': 'true',
    'BUILD_HANDOFF_ALLOWED': 'true',
}


def write_status(path, values):
    if values is not None:
        path.write_text(''.join(f'{k}={v}\n' for k, v in values.items()))


class APKArchiveSkip(unittest.TestCase):
    def setUp(self):
        self.cfg = yaml.safe_load((ROOT / '.circleci/config.yml').read_text())
        self.steps = self.cfg['jobs']['brave-android-staged-build']['steps']
        self.gate = next(s['run']['command'] for s in self.steps
                         if isinstance(s, dict) and s.get('run', {}).get('name') == NAME)

    def execute(self, apk=None, build=None, stage=1, command=None):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            state = root / 'brave-work/.sandium'
            state.mkdir(parents=True)
            scripts = root / '.circleci/scripts'
            scripts.mkdir(parents=True)
            shutil.copy2(ROOT / '.circleci/scripts/check-apk-completion-marker.py', scripts)
            write_status(state / 'apk-completion-status.txt', apk)
            write_status(state / 'build-stage-status.txt', build)
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            agent = bin_dir / 'circleci-agent'
            agent.write_text('#!/bin/bash\nset -eu\ntest "$*" = "step halt"\ntouch "$CIRCLE_WORKING_DIRECTORY/halted"\n')
            agent.chmod(0o755)
            env = dict(os.environ, CIRCLE_WORKING_DIRECTORY=str(root), SANDIUM_STAGE=str(stage),
                       CIRCLE_SHA1='example-revision',
                       PATH=str(bin_dir) + ':' + os.environ['PATH'])
            result = subprocess.run(['bash', '-c', command or self.gate], env=env,
                                    text=True, capture_output=True, timeout=5)
            halted = (root / 'halted').exists()
            return result.returncode, halted, result.stdout + result.stderr

    def test_verified_apk_halts_every_stage(self):
        for stage in range(1, 6):
            with self.subTest(stage=stage):
                code, halted, output = self.execute(VALID, stage=stage)
                self.assertEqual(code, 0, output)
                self.assertTrue(halted)
                self.assertIn('large handoff archive skipped', output)

    def test_stage_one_only_reuses_verified_same_workflow_and_revision_apk(self):
        group = next(s['when'] for s in self.steps if isinstance(s, dict)
                     and any(c.get('restore_cache', {}).get('name') ==
                             'Restore verified APK marker from this workflow and revision'
                             for c in s.get('when', {}).get('steps', [])))
        self.assertEqual(group['condition']['equal'], [1, '<< parameters.stage_index >>'])
        cache, gate = group['steps']
        self.assertEqual(cache['restore_cache']['keys'],
                         ['sandium-official-apk-complete-v1-{{ .Branch }}-{{ .Revision }}-'
                          '{{ .Environment.CIRCLE_WORKFLOW_ID }}-stage-1'])
        # A fresh workflow for the same revision must not borrow an old
        # marker and then halt without a marker its own stage 2 can restore.
        key_template = cache['restore_cache']['keys'][0]
        old_key = key_template.replace('{{ .Environment.CIRCLE_WORKFLOW_ID }}', 'old-workflow')
        new_key = key_template.replace('{{ .Environment.CIRCLE_WORKFLOW_ID }}', 'new-workflow')
        self.assertFalse(old_key.startswith(new_key))
        command = gate['run']['command']
        for marker, expected in [(VALID, True), (None, False),
                                 (dict(VALID, APK_REMOVALS_VALID='false'), False)]:
            code, halted, output = self.execute(marker, command=command)
            self.assertEqual(code, 0, output)
            self.assertEqual(halted, expected, output)

    def test_incomplete_attested_slice_continues_handoff(self):
        for apk in (None, {'BUILD_FINISHED': 'false'}):
            code, halted, output = self.execute(apk, TIMEOUT)
            self.assertEqual(code, 0, output)
            self.assertFalse(halted)
            self.assertIn('CHECKPOINT_HANDOFF=REQUIRED', output)

    def test_unverified_completed_build_fails_without_archive(self):
        for key in VALID:
            for value in (None, 'false', 'not_checked'):
                with self.subTest(key=key, value=value):
                    invalid = dict(VALID)
                    if value is None:
                        del invalid[key]
                    else:
                        invalid[key] = value
                    code, halted, output = self.execute(invalid, {'BUILD_REASON': 'BUILD_COMMAND_SUCCESS'})
                    self.assertNotEqual(code, 0, output)
                    self.assertFalse(halted)
                    self.assertIn('refusing archive', output)

    def test_missing_or_unattested_status_cannot_handoff(self):
        cases = [None, {}, {'BUILD_EXIT_CODE': '124'}, {'BUILD_REASON': 'ACTION_FAILED'}]
        for key in TIMEOUT:
            invalid = dict(TIMEOUT)
            del invalid[key]
            cases.append(invalid)
        for build in cases:
            code, halted, output = self.execute(build=build)
            self.assertNotEqual(code, 0, output)
            self.assertFalse(halted)

    def test_publication_and_small_marker_save_precede_gate(self):
        index = next(i for i, s in enumerate(self.steps)
                     if isinstance(s, dict) and s.get('run', {}).get('name') == NAME)
        self.assertEqual('Save small revision-scoped verified APK marker',
                         self.steps[index - 1]['save_cache']['name'])
        self.assertEqual('Record APK completion marker', self.steps[index - 2]['run']['name'])
        self.assertEqual('brave-apk', self.steps[index - 3]['store_artifacts']['path'])
        self.assertEqual('Export APK status and artifacts', self.steps[index - 4]['run']['name'])
        self.assertEqual('Validate Brave checkpoint before saving',
                         self.steps[index + 1]['when']['steps'][0]['run']['name'])
        self.assertNotEqual(self.steps[index]['run'].get('when'), 'always')
        # A native halt skips every subsequent expensive operation and final gate.
        after = str(self.steps[index + 1:])
        self.assertIn('archive-brave-workspace.sh archive', after)
        self.assertIn('Save FULL MODE parallel stage handoff shards', after)
        self.assertIn('Final five-stage completion gate', after)

    def test_downstream_halts_before_restore_or_preparation(self):
        for stage in range(2, 6):
            block = self.steps[stage]['when']
            self.assertEqual([stage, '<< parameters.stage_index >>'], block['condition']['equal'])
            keys = block['steps'][0]['restore_cache']['keys']
            self.assertEqual(stage - 1, len(keys))
            for key in keys:
                self.assertIn('{{ .Revision }}-{{ .Environment.CIRCLE_WORKFLOW_ID }}', key)
            command = block['steps'][1]['run']['command']
            self.assertIn('check-apk-completion-marker.py', command)
            self.assertIn('circleci-agent step halt', command)

    def test_active_config_equals_generated_candidate(self):
        self.assertEqual((ROOT / '.circleci/config.yml').read_bytes(),
                         (ROOT / '.circleci/original-full/candidate.yml').read_bytes())


if __name__ == '__main__':
    unittest.main()
