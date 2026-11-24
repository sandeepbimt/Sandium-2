"""Run the CI staging writer with a vendor-only stage and nested native additions."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from restore_only_feature import POSTIMAGES, Overlay, sha
import restore_only_port1442 as port


class StagePort1442(unittest.TestCase):
    def test_bridge_requires_both_exact_paths(self):
        names = sorted(port.BRIDGE)
        decision = {'staged_vendor_delta': {}}
        self.assertEqual({}, port.staged_deltas(decision))
        decision['staged_bridge_delta'] = {name: {} for name in names}
        self.assertEqual(decision['staged_bridge_delta'], port.staged_deltas(decision))
        for candidate in (
            {names[0]: {}},
            {**decision['staged_bridge_delta'], 'brave/x.rs': {}},
        ):
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(ValueError, 'bridge path'):
                    port.staged_deltas({**decision, 'staged_bridge_delta': candidate})
        with self.assertRaisesRegex(ValueError, 'vendor path'):
            port.staged_deltas({**decision, 'staged_vendor_delta': {names[0]: {}}})

    def test_validate_entire_bridge_before_replacing_any_source(self):
        names = sorted(port.BRIDGE)
        originals = {name: b'existing' + name.encode() for name in names}
        updates = {name: b'reviewed' + name.encode() for name in names}
        records = {name: {'before': sha(originals[name]), 'after': sha(updates[name])}
                   for name in names}
        review = {'manifest_sha256': 'exact-feature', 'staged_vendor_delta': {},
                  'staged_bridge_delta': records}
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            staging = root / 'stage'
            receipt = staging / 'source-receipt.json'
            overlay = Overlay('exact-feature',
                              {n: (None, r['after'], '644') for n, r in records.items()},
                              root, (), ())
            for name, record in records.items():
                src = staging / name
                src.parent.mkdir(parents=True, exist_ok=True)
                src.write_bytes(originals[name])
                dest = root / POSTIMAGES / record["after"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(updates[name])
            original_receipt = json.dumps({'sha256': {n: r['before'] for n, r in records.items()}})
            receipt.write_text(original_receipt)
            malformed = staging / names[1]
            malformed.write_bytes(b'tampered')
            with patch.object(port, 'ROOT', root), patch.object(port, 'proof', return_value=review):
                with self.assertRaisesRegex(ValueError, 'staged bytes'):
                    port.prepare_stage(staging, overlay)
                self.assertEqual(original_receipt, receipt.read_text())
                self.assertEqual(originals[names[0]], (staging / names[0]).read_bytes())
                malformed.write_bytes(originals[names[1]])
                port.prepare_stage(staging, overlay)
            self.assertEqual(updates, {n: (staging / n).read_bytes() for n in names})
            self.assertEqual({n: r['after'] for n, r in records.items()},
                             json.loads(receipt.read_text())['sha256'])

    def test_nested_native_sources_are_created_and_receipted(self):
        name = 'components/sandium_adblock/body_sniffer/BUILD.gn'
        payload = b'new body sniffer target'
        digest = sha(payload)
        identity = 'exact-feature'
        reviewed = {'manifest_sha256': identity, 'staged_vendor_delta': {}}
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            staging = root / 'stage'
            staging.mkdir()
            receipt = staging / 'source-receipt.json'
            receipt.write_text('{"sha256": {}}')
            post = root / POSTIMAGES / digest
            post.parent.mkdir(parents=True)
            post.write_bytes(payload)
            overlay = Overlay(identity, {name: (None, digest, '644')}, root, (), ())
            self.assertFalse((staging / name).parent.exists())
            with patch.object(port, 'ROOT', root), patch.object(port, 'proof', return_value=reviewed):
                port.prepare_stage(staging, overlay)
                port.prepare_stage(staging, overlay)
            self.assertEqual(payload, (staging / name).read_bytes())
            self.assertEqual({name: digest}, json.loads(receipt.read_text())['sha256'])


if __name__ == '__main__':
    unittest.main()
