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
