import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import preflight as p

class SourceAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.mock = patch.object(p,"SOURCE",self.path)
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.addCleanup(self.tmp.cleanup)

    def write(self, **overrides):
        a = self.path/"bare-arm64.gn"
        f = self.path/"rawb-m158.patch.zst"
        a.write_text("is_desktop_android = true\n")
        f.write_bytes(b"test fixture")
        d = {"bare":p.BARE,"chromium":p.TARGET,"depot_tools":p.DEPS,"patch_count":346,
             "bundled_ublock_sha256":p.CRX_SHA,"contains_brave_adblock":False,"contains_raws_overlay":False,
             "contains_1442_port":False,"remaining_holds":0,"source_admitted_for_graph":True,
             "upstream_bare_extension_policy":True,"graph_only":True,
             "patch_zstd_sha256":p.sha(f),"gn_args_sha256":p.sha(a)}
        d.update(overrides)
        (self.path/"source-admission.json").write_text(json.dumps(d))
        return f

    def test_missing(self):
        with self.assertRaisesRegex(ValueError,"No reviewed"):
            p.admission()

    def test_not_accepted_with_missing_install_policy(self):
        self.write(upstream_bare_extension_policy=False)
        with self.assertRaisesRegex(ValueError,"admission has not been proven"):
            p.admission()

    def test_not_accepted_with_344_policy_hold(self):
        self.write(remaining_holds=1)
        with self.assertRaisesRegex(ValueError,"admission has not been proven"):
            p.admission()

    def test_not_accepted_with_old_sanb(self):
        self.write(contains_brave_adblock=True)
        with self.assertRaisesRegex(ValueError,"admission has not been proven"):
            p.admission()

    def test_checked_digest(self):
        f=self.write()
        self.assertEqual(p.admission()["chromium"],p.TARGET)
        f.write_bytes(b"tamper")
        with self.assertRaisesRegex(ValueError,"digest"):
            p.admission()
