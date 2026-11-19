#!/usr/bin/env python3
import copy
import importlib.util
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('resume', Path(__file__).with_name('resume-official-1394.py'))
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)

class ResumeTests(unittest.TestCase):
    def test_manifest_exact(self):
        good = {'schema_version': 2, 'format': 'independent-tar+zstd-shards',
                'workers': 8, 'shards': [{}]*8, 'checkpoint_manifest': dict(r.EXPECTED)}
        r.validate_manifest(good)
        for key in r.EXPECTED:
            bad = copy.deepcopy(good); bad['checkpoint_manifest'][key] = 'wrong'
            with self.subTest(key=key), self.assertRaises(ValueError): r.validate_manifest(bad)
        for workers in (1, 4, 9):
            bad = copy.deepcopy(good); bad['workers'] = workers
            with self.assertRaises(ValueError): r.validate_manifest(bad)

    def test_official_gn(self):
        good = '\n'.join(f'{k} = {v}' for k,v in r.GN.items())
        r.validate_gn(good)
        for key in r.GN:
            bad = '\n'.join(f'{k} = {v}' for k,v in r.GN.items() if k != key)
            with self.subTest(key=key), self.assertRaises(ValueError): r.validate_gn(bad)
        with self.assertRaises(ValueError):
            r.validate_gn(good.replace('is_official_build = true', 'is_official_build = false'))
        with self.assertRaises(ValueError): r.validate_gn(good+'\nis_official_build = true')

    def test_generated_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            generated='\n'.join(f'{k} = {v}' for k,v in r.GN.items())
            (out/'args_generated.gni').write_text(generated)
            good='import("//out/android_Release_arm64/args_generated.gni")'
            (out/'args.gn').write_text('# comment\n'+good+'\n# extra args')
            r.validate_gn_files(out)
            for bad in ('# '+good, good+'\n'+good, good+'\nis_official_build = false',
                        good+'\nimport("//other.gni")', good+'\nif (true) {}'):
                (out/'args.gn').write_text(bad)
                with self.subTest(wrapper=bad), self.assertRaises(ValueError): r.validate_gn_files(out)
            (out/'args.gn').write_text(good)
            (out/'args_generated.gni').write_text(generated.replace('is_official_build = true','is_official_build = false'))
            with self.assertRaises(ValueError): r.validate_gn_files(out)

    def test_pinned_digest_and_size_are_required(self):
        payload = {'schema_version': 2, 'format': 'independent-tar+zstd-shards',
                   'workers': 8, 'shards': [{}]*8, 'checkpoint_manifest': dict(r.EXPECTED),
                   'archive_bytes': r.ARCHIVE_BYTES}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root/'brave-workspace-checkpoint.manifest.json'
            manifest.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                r.validate_checkpoint(root)
            with patch.object(r, 'MANIFEST_SHA', r.digest(manifest)):
                r.validate_checkpoint(root)
            payload['archive_bytes'] -= 1
            manifest.write_text(json.dumps(payload))
            with patch.object(r, 'MANIFEST_SHA', r.digest(manifest)), self.assertRaisesRegex(ValueError, 'archive size'):
                r.validate_checkpoint(root)

    def test_verified_seed_outputs_are_retired_without_touching_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            apk = root/r.APK_PATH
            apk.parent.mkdir(parents=True)
            apk.write_bytes(b'seed APK evidence')
            graph = apk.parent.parent/'build.ninja'
            graph.write_text('keep')
            state = root/'brave-work/.sandium'
            state.mkdir()
            names = ['apk-completion-status.txt', 'restored-apk-valid', 'checkpoint-manifest.txt']
            for name in names:
                (state/name).write_text('keep only provenance')
            with self.assertRaisesRegex(ValueError, 'APK size or SHA256'):
                r.retire_seed_outputs(root)
            self.assertTrue(apk.exists())
            self.assertTrue(all((state/name).exists() for name in names))
            with patch.object(r, 'APK_BYTES', apk.stat().st_size), patch.object(r, 'APK_SHA', r.digest(apk)):
                r.retire_seed_outputs(root)
            self.assertFalse(apk.exists())
            self.assertEqual(graph.read_text(), 'keep')
            self.assertTrue((state/names[-1]).exists())
            self.assertFalse(any((state/name).exists() for name in names[:-1]))

    def test_config(self):
        text=(ROOT/'.circleci/config.yml').read_text()
        config=yaml.safe_load(text)
        self.assertEqual(config['parameters']['sandium_build_mode']['enum'], ['full'])
        steps=config['jobs']['brave-android-staged-build']['steps']
        group=next(s['when'] for s in steps if 'when' in s and any(
            'restore_cache' in x and x['restore_cache'].get('name')=='Restore exact readback-verified official 1402 stage 2 reference'
            for x in s['when']['steps']))
        caches=[x['restore_cache']['keys'] for x in group['steps'] if 'restore_cache' in x]
        self.assertEqual(caches, [['sandium-official-handoff-v1-fix/1394-official-lint-'+r.WORKFLOW+'-stage-2']])
        retire_idx = next(i for i,s in enumerate(steps) if 'when' in s and any(
            'retire-seed-outputs' in x.get('run', {}).get('command', '') for x in s['when']['steps']))
        self.assertEqual(steps[retire_idx]['when']['condition'], {'equal': [1, '<< parameters.stage_index >>']})
        reclaim_idx = next(i for i,s in enumerate(steps) if isinstance(s, dict) and s.get('run', {}).get('name') ==
                           'Reclaim verified restored transport before official build')
        self.assertLess(retire_idx, reclaim_idx)
        self.assertIn('postrestore', steps[retire_idx-1]['run']['command'])
        self.assertNotIn('fixed_reference.py', str(steps))
        self.assertEqual(text.count('- fix/1394-official-lint'),5)
        self.assertIn('EXCEPTIONAL_ARCHIVE=REQUIRED',text)
        self.assertIn('export SANDIUM_ARCHIVE_WORKERS=8',text)
        self.assertIn('official-checkpoint-safety.py',text)
        self.assertIn('bash .circleci/scripts/archive-brave-workspace.sh restore',text)

if __name__ == '__main__': unittest.main()
