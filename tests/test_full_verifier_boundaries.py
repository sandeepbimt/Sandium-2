"""Exercise the real Full verifier CLI in clean processes, not patched imports."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FullVerifierBoundaries(unittest.TestCase):
    def verify(self, count, fault=None, driver='full_driver.py'):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / '.checkpoint-state'
            state.mkdir()
            layers = []
            head = 'base'
            for index in range(count):
                layer = dict(id=f'layer-{index}', parent=head, expires_at=time.time()+86400)
                layers.append(layer)
                head = layer['id']
            payload = dict(scope='sandium-exp-single-v1-bridge-test',
                compatibility='brave-44a84b1-chromium-d331de3-arm64-release-single-v1',
                kind='legacy-bridge-v1', pipeline=1,
                plan=dict(base=dict(id='base', expires_at=time.time()+86400), layers=layers, head=head))
            if fault == 'parent': layers[-1]['parent'] = 'wrong'
            if fault == 'expired': layers[-1]['expires_at'] = 1
            if fault == 'head': payload['plan']['head'] = 'wrong'
            encoded = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
            receipt = dict(id=hashlib.sha256(encoded).hexdigest(), payload=payload)
            if fault == 'digest': receipt['id'] = 'wrong'
            proof = dict(receipt=receipt['id'], head=payload['plan']['head'])
            if fault == 'proof': proof['head'] = 'wrong'
            (state/'selected.json').write_text(json.dumps(receipt))
            (state/'restored-proof.json').write_text(json.dumps(proof))
            env = dict(os.environ, CIRCLE_WORKING_DIRECTORY=str(root),
                SANDIUM_EXPERIMENT_SCOPE=payload['scope'], SANDIUM_PIPELINE_NUMBER='2')
            return subprocess.run([sys.executable, str(ROOT/'.circleci/bridge'/driver),
                'verify-restored'], env=env, text=True, capture_output=True)

    def test_full_accepts_through_sixteen_in_fresh_processes(self):
        for count in (0, 7, 8, 11, 15, 16):
            with self.subTest(count=count):
                result = self.verify(count)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_full_refuses_seventeen(self):
        result = self.verify(17)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unbounded delta chain', result.stderr)

    def test_integrity_and_exact_proof_are_not_relaxed(self):
        for fault in ('parent', 'expired', 'head', 'digest', 'proof'):
            with self.subTest(fault=fault):
                self.assertNotEqual(self.verify(8, fault).returncode, 0)

    def test_sixteen_real_deltas_replay_and_roll_up(self):
        # Separate interpreter also proves the Full sparse/CLI setup is loaded.
        code = r"""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import full_driver as f
from rollup import rollup
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory); work=root/'work'; work.mkdir()
    (work/'value').write_text('0')
    head='base'; layers=[]
    for index in range(16):
        before=f.bridge.begin(work,head,str(index))
        (work/'value').write_text(str(index+1))
        archive=root/f'{index}.zip'
        result=f.bridge.capture(work,before,str(index),archive,lambda:None)
        layers.append(dict(archive=str(archive),id=result['id'],parent=head))
        head=result['id']
    dest=root/'dest'; dest.mkdir(); (dest/'value').write_text('0')
    assert f.sparse_restore.apply_chain(dest,layers,'base') == head
    assert (dest/'value').read_text() == '16'
    merged=rollup('base',[dict(path=x['archive'],id=x['id']) for x in layers],root/'merged.zip')
    replay=root/'replay'; replay.mkdir(); (replay/'value').write_text('0')
    f.sparse_restore.apply_chain(replay,[dict(archive=str(root/'merged.zip'),id=merged['id'],parent='base')],'base')
    assert (replay/'value').read_text() == '16'
"""
        result=subprocess.run([sys.executable,'-c',code,str(ROOT/'.circleci/bridge')],text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_fixture_reproduces_old_entrypoint_failure(self):
        result = self.verify(8, driver='driver.py')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unbounded delta chain', result.stderr)


if __name__ == '__main__':
    unittest.main()
