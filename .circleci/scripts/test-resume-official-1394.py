#!/usr/bin/env python3
import copy
import importlib.util
from pathlib import Path
import unittest
import tempfile
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

    def test_config(self):
        text=(ROOT/'.circleci/config.yml').read_text()
        config=yaml.safe_load(text)
        self.assertEqual(config['parameters']['sandium_build_mode']['enum'], ['full'])
        steps=config['jobs']['brave-android-staged-build']['steps']
        group=next(s['when'] for s in steps if 'when' in s and any(
            'restore_cache' in x and x['restore_cache'].get('name')=='Restore exact verified official 1394 stage 3 checkpoint'
            for x in s['when']['steps']))
        caches=[x['restore_cache']['keys'] for x in group['steps'] if 'restore_cache' in x]
        self.assertEqual(caches, [['sandium-official-handoff-v1-fix/official-checkpoint-1392-'+r.WORKFLOW+'-stage-3']])
        self.assertNotIn('fixed_reference.py', str(steps))
        self.assertEqual(text.count('- fix/1394-official-lint'),5)
        self.assertIn('EXCEPTIONAL_ARCHIVE=REQUIRED',text)
        self.assertIn('export SANDIUM_ARCHIVE_WORKERS=8',text)
        self.assertIn('official-checkpoint-safety.py',text)
        self.assertIn('bash .circleci/scripts/archive-brave-workspace.sh restore',text)

if __name__ == '__main__': unittest.main()
