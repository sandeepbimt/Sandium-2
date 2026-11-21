import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools"))
import sanb_capacity_audit as c


class CapacityAudit(unittest.TestCase):
    def test_exact_large_same_image_and_route(self):
        config=(ROOT/".circleci/config.yml").read_text()
        cap=config.split("  sanb-capacity-audit:\n",1)[1].split("  sanb-android-arm64:\n",1)[0]
        build=config.split("  sanb-android-arm64:\n",1)[1].split("\nworkflows:",1)[0]
        for header in ("machine:","image: ubuntu-2404:current","resource_class: large"):
            self.assertIn(header,cap)
            self.assertIn(header,build)
        self.assertNotIn("working_directory:",cap+build)  # Same platform default.
        self.assertIn('pipeline.parameters.sanb_mode == "capacity-audit"', config)
        self.assertIn('pipeline.parameters.sanb_mode != "capacity-audit"', config)
        self.assertIn("90s python3 -u tools/sanb_capacity_audit.py", cap)
        self.assertNotRegex(cap,r"(?im)^\s*(?:context|attach_workspace|save_cache|restore_cache|persist_to_workspace):")
        self.assertNotRegex(cap,r"\b(?:autoninja|gclient|gn|install-build-deps)\b")

    def test_user_available_not_reserved_disk_and_threshold(self):
        kib=4096
        blocks=(c.REQUIRED_FREE_BYTES-4096)//kib
        data=SimpleNamespace(f_frsize=kib,f_bsize=kib,f_blocks=blocks+300,
                             f_bavail=blocks,f_bfree=blocks+100,
                             f_favail=28,f_ffree=30,f_files=100)
        with mock.patch.object(c.os,"statvfs",return_value=data):
            x=c.disk_snapshot(ROOT)
            self.assertEqual(x["inodes_available"],28)
        self.assertFalse(c.eligibility(x["disk_free_bytes_user_available"]))
        self.assertTrue(c.eligibility(x["disk_raw_free_bytes_including_reserved"]))
        self.assertTrue(c.eligibility(c.REQUIRED_FREE_BYTES))
        self.assertEqual(c.REQUIRED_FREE_BYTES,139586437120)

    def test_ancestor_cgroup_limits_and_optional_telemetry(self):
        with tempfile.TemporaryDirectory() as name:
            base=Path(name); proc=base/"proc"; s=base/"sys"
            (proc/"self").mkdir(parents=True); (s/"nested/child").mkdir(parents=True)
            (proc/"self/cgroup").write_text("0::/nested/child\n")
            (s/"nested/child/cpu.max").write_text("max 100000\n")
            (s/"nested/cpu.max").write_text("250000 100000\n")
            (s/"cpu.max").write_text("400000 100000\n")
            (s/"nested/child/memory.max").write_text("max\n")
            (s/"nested/memory.max").write_text("16000000000\n")
            (s/"nested/child/memory.current").write_text("12345\n")
            g=c.cgroup_snapshot(proc,s)
            self.assertEqual(g["telemetry"],"v2")
            self.assertEqual(g["cpu_quota_cores"],2.5)
            self.assertEqual(g["memory_limit_bytes"],16000000000)
            self.assertEqual(g["memory_usage_bytes"],12345)
            (proc/"self/cgroup").write_text("0::/../../escape\n")
            self.assertEqual(c.cgroup_snapshot(proc,s)["telemetry"],"unavailable")

    def test_measurement_below_floor_is_green_but_not_build_eligible(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            def io(args,d):
                self.assertEqual(d,root)
                if args[0]=="git": return "a"*40+"\n"
                self.assertEqual(args[0],"df")
                self.assertEqual(args[-2:],["--",str(root)])
                return "only target mount\n"
            free=12*2**30
            with (mock.patch.object(c,"command",side_effect=io),
                  mock.patch.object(c,"disk_snapshot",return_value={"disk_free_bytes_user_available":free}),
                  mock.patch.object(c.shutil,"disk_usage",return_value=SimpleNamespace(free=free)),
                  mock.patch.object(c,"host_snapshot",return_value={"logical_cpus":4}),
                  mock.patch.object(c,"cgroup_snapshot",return_value={"telemetry":"v2"})):
                self.assertEqual(c.main(root,{"CIRCLE_BRANCH":c.BRANCH,"CIRCLE_SHA1":"a"*40,
                                              "RAWS_TEST_KEYSTORE_B64":"not printed"}),0)
            final=json.loads((root/c.OUTPUT/"status.json").read_text())
            self.assertTrue(final["measured"])
            self.assertIs(final["eligible_for_130_gib"],False)
            self.assertFalse(any(final[x] for x in ("apk_produced","build_admission","compiler_started","checkpoint_saved")))
            self.assertEqual((root/c.OUTPUT/"df.txt").read_text(),"only target mount\n")
            self.assertNotIn("KEYSTORE",(root/c.OUTPUT/"status.json").read_text())

    def test_failed_measurement_is_unknown_and_stops(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            with mock.patch.object(c,"command",side_effect=AssertionError("No read before guard")):
                self.assertEqual(c.main(root,{"CIRCLE_BRANCH":"raw-sandium/official158"}),1)
            final=json.loads((root/c.OUTPUT/"status.json").read_text())
            self.assertIs(final["measured"],False)
            self.assertIsNone(final["eligible_for_130_gib"])
            self.assertFalse((root/c.OUTPUT/"df.txt").exists())
