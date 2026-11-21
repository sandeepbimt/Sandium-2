import json
import os
from pathlib import Path
import tempfile
import struct
import time
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / "tools"))
import sanb_ci as s
import sanb_unsigned as u

ELF_ARM64 = b"\x7fELF\x02\x01" + bytes(12) + b"\xb7\x00"
EXACT = dict(schema=1, bare=s.BARE, chromium=s.CHROMIUM, version=s.VERSION,
             android_desktop=True, embedded_ublock=False, patch_sha256="b"*64)


class SanB(unittest.TestCase):
    def test_exact_source_plan(self):
        self.assertEqual(s.verify_source_receipt(EXACT), EXACT)
        for k,v in dict(schema=True, bare="c"*40, chromium="c"*40, version="157",
                        android_desktop=1, embedded_ublock=True, patch_sha256="b").items():
            with self.subTest(k=k):
                with self.assertRaises(ValueError):
                    s.verify_source_receipt({**EXACT,k:v})

    def test_project_credentials_are_not_inherited_into_commands(self):
        with self.assertRaisesRegex(ValueError,"credentials"):
            s.deny_preexisting_keys({"RAWS_TEST_KEYSTORE_B64":""})
        with self.assertRaisesRegex(ValueError,"credentials"):
            s.deny_preexisting_keys({"SANB_KEY_PASSWORD":"not printed"})
        env=s.subprocess_env({"PATH":"/bin","HOME":"/tmp","BUILDBUDDY_TOKEN":"none",
                              "SISO_REAPI_ADDRESS":"none","CIRCLE_TOKEN":"none"},Path("/safe"))
        self.assertEqual(env["PATH"],"/safe:/bin")
        self.assertFalse({"BUILDBUDDY_TOKEN","SISO_REAPI_ADDRESS","CIRCLE_TOKEN"} & env.keys())

    def test_exact_release_args_and_separation(self):
        source=(ROOT/"ci/sanb-args.gn").read_text()
        s.verify_build_args(source)
        for changed in (source+'use_remoteexec = true\n',source.replace('arm64','x64'),
                        source.replace(s.PACKAGE,"org.chromium.chrome"),
                        source.replace("is_desktop_android = true","is_desktop_android = false")):
            with self.assertRaises(ValueError):
                s.verify_build_args(changed)
        ci=(ROOT/".circleci/config.yml").read_text()
        self.assertIn("  SanB:\n",ci)
        self.assertIn("    default: false",ci)
        self.assertIn("equal: [sanb/official158, << pipeline.git.branch >>]",ci)
        self.assertNotRegex(ci,r"(?im)^\s*(?:context|attach_workspace|save_cache|restore_cache|triggers):")
        self.assertNotIn("raw-sandium/official158",ci)

    def test_arm64_only_unsigned_and_no_ublock(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"fixture.apk"
            for extra in (None,"assets/ublock_origin.crx","assets/cjpalhdlnbpafiamejdnhcphjbkeiagm",
                          "META-INF/KEY.RSA","lib/x86_64/libother.so"):
                with self.subTest(extra=extra):
                    with zipfile.ZipFile(p,"w") as z:
                        z.writestr("AndroidManifest.xml",b"manifest")
                        z.writestr("lib/arm64-v8a/libchrome.so",ELF_ARM64)
                        if extra: z.writestr(extra,b"bad")
                    if extra:
                        with self.assertRaises(ValueError): s.verify_zip(p)
                    else:
                        s.verify_zip(p)
                        with zipfile.ZipFile(p) as z: central=z.start_dir
                        data=p.read_bytes()
                        # Insert only a synthetic magic marker before an intact central dir.
                        raw = bytearray(data[:central]+s.SIG_BLOCK+data[central:])
                        eocd = raw.rfind(b'PK\x05\x06')
                        struct.pack_into("<I", raw, eocd+16, central+len(s.SIG_BLOCK))
                        p.write_bytes(raw)
                        with zipfile.ZipFile(p) as z: self.assertIsNone(z.testzip())
                        with self.assertRaisesRegex(ValueError,"v2/v3"):
                            s.verify_zip(p)
            with zipfile.ZipFile(p,"w") as z:
                z.writestr("AndroidManifest.xml",b"manifest")
                z.writestr("lib/arm64-v8a/libchrome.so",b"not an ELF")
            with self.assertRaisesRegex(ValueError,"ELF64 AArch64"):
                s.verify_zip(p)

    def test_package_label_non_debug_native_abi(self):
        good=f"package: name='{s.PACKAGE}' versionCode='1'\napplication-label:'SanB'\nnative-code: 'arm64-v8a'\n"
        s.verify_badging(good)
        for bad in (good+"application-debuggable\n",good.replace("SanB","Bare"),good.replace(s.PACKAGE,"com.bare"),
                    good.replace("'arm64-v8a'","'arm64-v8a' 'armeabi-v7a'")):
            with self.assertRaises(ValueError): s.verify_badging(bad)

    def test_graph_bans_signing_and_extension_only(self):
        src=Path("/src");out=src/s.OUT
        values=dict(args="--output-apk=abc/ChromePublic.apk\n",inputs="//generic/input\n",
                    outputs="//out/SanB-arm64/apks/ChromePublic.apk\n",deps=":generic\n")
        def query(arguments,*rest):
            return values[arguments[4]]
        with mock.patch.object(s,"checked",side_effect=query):
            s.verify_apk_graph(src,out,"gn",{})
            for field,bad in (("args","--key-name=fallback"),("inputs","//other/user.keystore"),
                              ("outputs","chrome.apk.idsig"),("deps","//data/u_block_origin:bundle")):
                values[field]+=bad+"\n"
                with self.assertRaises(ValueError): s.verify_apk_graph(src,out,"gn",{})
                values[field]=values[field].replace(bad+"\n","")

    def test_pinned_packager_passes_and_refuses_overlap(self):
        fixture=os.getenv("SANB_PINNED_PUBLIC_FIXTURE")
        if fixture is None:
            # Ensure a wrong/missing tree cannot accidentally receive any edits.
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(ValueError): u.postimages(Path(td))
            return
        import shutil
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);shutil.copytree(fixture,p,dirs_exist_ok=True)
            values=u.apply(p)
            self.assertEqual(set(values),{p/u.INTERNAL,p/u.RULES})
            u.verify(values)
            self.assertIn(b"sanb_unsigned_apk = false", (p/u.RULES).read_bytes())
            self.assertIn(b'== "chrome_public_apk"',(p/u.RULES).read_bytes())
            with self.assertRaises(ValueError): u.postimages(p)

    def test_pinned_worker_stops_when_source_not_ready_or_space_missing(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);folder=p/".sanb-artifacts";folder.mkdir()
            (folder/"epoch").write_text(str(time.time()))
            (p/"tools").mkdir();(p/"tools/sanb_source.py").write_text("# Fixture adapter\n")
            (p/"ci").mkdir();(p/"ci/sanb-args.gn").write_bytes((ROOT/"ci/sanb-args.gn").read_bytes())
            def source_plan(plan):
                def run(*a,**kw):
                    (folder/"source-plan.json").write_text(json.dumps(plan))
                return run
            with mock.patch.object(s,"read_current",return_value="a"*40):
                with mock.patch.object(s.shutil,"disk_usage",return_value=mock.Mock(free=s.MIN_GIB*2**30)):
                    with mock.patch.object(s,"run",side_effect=source_plan(EXACT)):
                        self.assertEqual(s.main("preflight",p,{}),0)
                        status=json.loads((folder/"status.json").read_text())
                        self.assertEqual(status["result"],"preflight_passed_no_compile")
                        self.assertFalse(status["apk_produced"])
                    with mock.patch.object(s,"run",side_effect=source_plan({**EXACT,"embedded_ublock":True})):
                        self.assertEqual(s.main("build",p,{}),1)
                        self.assertEqual(json.loads((folder/"status.json").read_text())["phase"],
                                         "static-source-proof")
                with mock.patch.object(s.shutil,"disk_usage",return_value=mock.Mock(free=45*2**30)):
                    with mock.patch.object(s,"run",side_effect=source_plan(EXACT)) as call:
                        self.assertEqual(s.main("build",p,{}),1)
                        self.assertEqual(call.call_count,1) # no gclient/gn/compile on low disk

    def test_worker_deadline_terminates_without_publishing(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            before=time.monotonic()
            with mock.patch.object(s,"actions_left",return_value=1):
                with self.assertRaisesRegex(TimeoutError,"test-timeout"):
                    s.run([sys.executable,"-c","import time; time.sleep(20)"],
                          cwd=p,env=os.environ,deadline=0,log=p/"compile.log",phase="test-timeout")
            self.assertLess(time.monotonic()-before,10)
            self.assertEqual([x.name for x in p.iterdir()],["compile.log"])
