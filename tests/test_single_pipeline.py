import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / '.circleci/checkpoint/driver.py'
sys.path.insert(0, str(ROOT / '.circleci/checkpoint'))
from checkpoint import scan


class SinglePipeline(unittest.TestCase):
    def test_complete_config_is_one_mode_and_noncanonical(self):
        config = yaml.safe_load((ROOT / '.circleci/config.yml').read_text())
        self.assertEqual(list(config['workflows']), ['sandium-full', 'sandium-checkpoint-maintenance'])
        # Maintenance is not a second APK build mode.
        maintenance=json.dumps(config['jobs']['maintain-full-checkpoint'])
        self.assertNotIn('bounded-build.sh',maintenance)
        self.assertIn('maintenance-capture',maintenance)
        self.assertNotIn('sandium_build_mode', config['parameters'])
        self.assertNotIn('run_experiment', config['parameters'])
        self.assertFalse(config['parameters']['run_build']['default'])
        self.assertFalse(config['parameters']['run_maintenance']['default'])
        self.assertFalse(config['parameters']['allow_seed_import']['default'])
        group = config['job-groups']['sandium-full-chain']['jobs']
        self.assertEqual(len(group), 8)
        for job in config['jobs'].values():
            for step in job['steps']:
                if isinstance(step, dict) and 'save_cache' in step:
                    key = step['save_cache']['key']
                    self.assertNotIn('sandium-brave-handoff', key)
                    self.assertNotIn('reference', key)
        for number in range(1, 6):
            steps = config['jobs'][f'full-stage-{number}']['steps']
            commands = [s['run']['command'] for s in steps if isinstance(s, dict) and 'run' in s]
            self.assertTrue(any('driver.py restore' in c for c in commands))
            self.assertTrue(any('bounded-build.sh' in c for c in commands))
            self.assertTrue(any('driver.py capture' in c for c in commands))
            self.assertTrue(any('driver.py publish' in c for c in commands))

    def test_driver_real_seed_stage_and_next_run_reconstruction(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache = root / 'native-cache'; cache.mkdir()
            env = dict(os.environ, SANDIUM_EXPERIMENT_REVIEWED='true', CIRCLE_PROJECT_REPONAME='Sandium-2',
                SANDIUM_EXPERIMENT_SCOPE='sandium-exp-single-v1-fixture', SANDIUM_ALLOW_SEED_IMPORT='true',
                SANDIUM_PIPELINE_NUMBER='20', CIRCLE_WORKFLOW_ID='workflow20', CIRCLE_SHA1='a'*40)
            def invoke(job, phase, stage, build, slot=None):
                args=[sys.executable,str(DRIVER),phase]
                if slot is not None:args += ['--slot',str(slot)]
                return subprocess.run(args,env=dict(env,CIRCLE_WORKING_DIRECTORY=str(job),SANDIUM_STAGE=str(stage),CIRCLE_BUILD_NUM=str(build)),
                    stdout=subprocess.PIPE,stderr=None,text=True,check=True)
            seed=root/'seed';seed.mkdir(); work=seed/'brave-work';work.mkdir()
            (work/'stable.o').write_bytes(bytes(range(256))*128)
            (work/'same-content.o').write_bytes(bytes(range(256))*128)
            (work/'same-content.o').chmod(0o755)
            (work/'modify.o').write_bytes(b'A')
            invoke(seed,'seed-select',0,1)
            invoke(seed,'seed-capture',0,1)
            shutil.copytree(seed/'.checkpoint-incoming',cache/'layer0') # native-save boundary simulation
            invoke(seed,'publish',0,1)
            first=root/'stage1';first.mkdir()
            shutil.copytree(seed/'.checkpoint-head',first/'.checkpoint-head')
            invoke(first,'select',1,2)
            shutil.copytree(cache/'layer0',first/'.checkpoint-incoming')
            invoke(first,'ingest',1,2,0)
            invoke(first,'restore',1,2)
            self.assertEqual(scan(work),scan(first/'brave-work'))
            self.assertNotEqual((first/'brave-work/stable.o').stat().st_ino,
                                (first/'brave-work/same-content.o').stat().st_ino)
            self.assertFalse(any((first/'.checkpoint-store/blobs').iterdir()))
            (first/'brave-work'/'modify.o').write_bytes(b'AB')
            invoke(first,'capture',1,2)
            shutil.copytree(first/'.checkpoint-incoming',cache/'layer1')
            invoke(first,'publish',1,2)
            plan=json.loads((first/'.checkpoint-head/receipt.json').read_text())['payload']['plan']
            self.assertEqual(len(plan['layers']),2)
            self.assertEqual(plan['layers'][1]['content_bytes'],2)
            second=root/'next-run';second.mkdir()
            shutil.copytree(first/'.checkpoint-head',second/'.checkpoint-head')
            env.update(SANDIUM_PIPELINE_NUMBER='21',CIRCLE_WORKFLOW_ID='workflow21',CIRCLE_SHA1='b'*40)
            invoke(second,'select',1,3)
            for index in (0,1):
                shutil.rmtree(second/'.checkpoint-incoming',ignore_errors=True)
                shutil.copytree(cache/f'layer{index}',second/'.checkpoint-incoming')
                invoke(second,'ingest',1,3,index)
            invoke(second,'restore',1,3)
            self.assertEqual(scan(first/'brave-work'),scan(second/'brave-work'))

    def test_host_install_is_separate_from_stage_one_source_work(self):
        source = (ROOT / '.circleci/scripts/prepare-brave-source.sh').read_text()
        helper = (ROOT / '.circleci/scripts/install-flow-host-deps.sh').read_text()
        stage_one = source.index('if [ "${BRAVE_STAGE_INDEX:?BRAVE_STAGE_INDEX is required}" = "1" ]; then')
        routing = source[source.index('if [ "$BRAVE_STAGE_INDEX" != "1" ]; then'):stage_one]
        self.assertIn('install-flow-host-deps.sh', routing)
        self.assertEqual(source[stage_one:].count('install-flow-host-deps.sh'), 1)
        self.assertNotIn('install-build-deps.sh --android', source)
        self.assertIn('./src/build/install-build-deps.sh --android', helper)
        self.assertIn('exit "$APT_FAILURE_CODE"', helper)
        for forbidden in ('git reset', 'git clean', 'pnpm run', 'apply-sandium'):
            self.assertNotIn(forbidden, helper)
        with tempfile.TemporaryDirectory() as tmp:
            helper_path = Path(tmp) / '.circleci/scripts/install-flow-host-deps.sh'
            helper_path.parent.mkdir(parents=True)
            helper_path.write_text('echo host-installed\n')
            for stage in range(1, 6):
                result = subprocess.run(['bash', '-euc', routing], env=dict(os.environ,
                    ROOT=tmp, BRAVE_STAGE_INDEX=str(stage)), capture_output=True, text=True, check=True)
                self.assertEqual(result.stdout.strip(), '' if stage == 1 else 'host-installed')

    def test_disk_guard_fails_closed(self):
        from unittest.mock import patch
        from collections import namedtuple
        import driver
        from checkpoint import CheckpointError
        usage = namedtuple('usage', 'total used free')
        with patch.object(driver.shutil, 'disk_usage', return_value=usage(100, 95, 5)):
            with self.assertRaisesRegex(CheckpointError, 'Insufficient disk'):
                driver.disk_guard('fixture', 6)
            driver.disk_guard('fixture', 5)

    def test_watchdog_silent_stall_and_progress_deadline(self):
        prefix = "import sys,time;sys.path.insert(0," + repr(str(ROOT / '.circleci/checkpoint')) + ");from progress import Watchdog,advance;"
        silent = subprocess.run([sys.executable, '-c', prefix +
            "exec('with Watchdog(2,stall_seconds=0.15,poll_seconds=0.02):\\n time.sleep(1)')"], capture_output=True, text=True)
        self.assertEqual(silent.returncode,124, silent.stderr)
        self.assertIn('no-measured-progress', silent.stdout)
        moving = subprocess.run([sys.executable, '-c', prefix +
            "exec('with Watchdog(0.25,stall_seconds=0.15,poll_seconds=0.02):\\n while True: advance(items=1); time.sleep(0.03)')"],
            env=dict(os.environ,FLOW_PROGRESS_INTERVAL_SECONDS='0.05'), capture_output=True,text=True)
        self.assertEqual(moving.returncode,124, moving.stderr)
        self.assertIn('deadline', moving.stdout)
        self.assertGreater(moving.stdout.count('FLOW_PROGRESS'),1)

    def test_build_reserves_checkpoint_and_native_save_time(self):
        from job_budget import build_seconds
        self.assertEqual(build_seconds(0,0),1200)
        self.assertEqual(build_seconds(0,700),860)
        self.assertEqual(700+build_seconds(0,700)+900+600+60+180,3300)
        with self.assertRaises(ValueError):
            build_seconds(0,1700)

    def test_restore_duplicate_copy_reports_chunks_and_preserves_bytes(self):
        from unittest.mock import patch
        import consume_restore
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source'
            target = Path(tmp) / 'target'
            source.write_bytes(b'x' * (2 * 1024**2 + 123))
            events = []
            with patch.object(consume_restore, 'advance', side_effect=lambda **kw: events.append(kw)):
                consume_restore.copy_measured(source, target)
            self.assertEqual(source.read_bytes(), target.read_bytes())
            self.assertNotEqual(source.stat().st_ino, target.stat().st_ino)
            self.assertEqual([e['bytes_done'] for e in events], [1024**2, 1024**2, 123])

    def test_false_review_stops_before_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=subprocess.run([sys.executable,str(DRIVER),'gate'],env=dict(os.environ,
                CIRCLE_WORKING_DIRECTORY=tmp,SANDIUM_EXPERIMENT_REVIEWED='false'),capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('review not confirmed',result.stderr)


if __name__=='__main__':
    unittest.main(verbosity=2)
