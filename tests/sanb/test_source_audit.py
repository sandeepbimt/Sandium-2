import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tools"))
import sanb_source_audit_ci as a
import sanb_bulk_context as replay


def blob(raw):
    return hashlib.sha1(f"blob {len(raw)}\0".encode()+raw, usedforsecurity=False).hexdigest()


class SourceAudit(unittest.TestCase):
    def test_exact_portable_driver_and_inventory(self):
        rows, paths = a.read_inventory(ROOT/a.INVENTORY)
        self.assertEqual((len(rows),len(paths)), (346,1166))
        self.assertEqual(a.digest((ROOT/a.REPLAY).read_bytes()), a.DRIVER_SHA)
        self.assertEqual(a.digest((ROOT/a.REPLAY_HELPER).read_bytes()), a.HELPER_SHA)
        self.assertEqual(rows[0]["id"], "0000001")
        for x in ("../escaped","a/.git/config","/absolute","x//y","a/./z","x\ny",":!foo"):
            with self.assertRaises(ValueError):
                a.validated_path(x)

    def test_distinct_filtered_route_no_compile_or_retention(self):
        text=(ROOT/".circleci/config.yml").read_text()
        self.assertIn('enum: [preflight, build, source-audit, capacity-audit]',text)
        self.assertIn('filters: pipeline.parameters.sanb_mode == "source-audit" and pipeline.git.branch == "sanb/official158"',text)
        self.assertIn('filters: pipeline.parameters.sanb_mode != "source-audit" and pipeline.parameters.sanb_mode != "capacity-audit" and pipeline.git.branch == "sanb/official158"',text)
        audit=text.split("  sanb-source-audit:\n",1)[1].split("  sanb-android-arm64:\n",1)[0]
        self.assertIn('test "<< pipeline.parameters.sanb_mode >>" = "source-audit"',audit)
        self.assertIn("destination: sanb-source-audit",audit)
        self.assertIn("23m python3 -u tools/sanb_source_audit_ci.py",audit)
        self.assertNotRegex(audit,r"(?im)\b(?:apk|autoninja|gclient|gn|restore_cache|save_cache|persist_to_workspace|context:)\b")

    def test_environment_does_not_retain_tokens_or_lazy_network(self):
        incoming={"PATH":"/bin","CIRCLE_TOKEN":"x","GITHUB_TOKEN":"x","RAWS_TEST_KEYSTORE_B64":"x",
                  "GIT_CONFIG_PARAMETERS":"x","http_proxy":"x"}
        public=a.env_for(incoming,network=True)
        offline=a.env_for(incoming,network=False)
        self.assertEqual(public["GIT_ALLOW_PROTOCOL"],"https")
        self.assertEqual(offline["GIT_ALLOW_PROTOCOL"],"")
        self.assertEqual(offline["GIT_NO_LAZY_FETCH"],"1")
        self.assertNotIn("GIT_CONFIG_PARAMETERS",public)
        for s in ("GITHUB_TOKEN","CIRCLE_TOKEN","RAWS_TEST_KEYSTORE_B64","http_proxy"):
            self.assertNotIn(s,public)

    def test_archive_only_expected_blobs_no_symlink_crx_or_wrong_bytes(self):
        for invalid in ("../bad", "unexpected-oid", "symlink", "crx", "content", None):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)
                dest=p/"artifacts"; dest.mkdir()
                archive=p/"sanb-pinned-preimages.tar.gz"
                expected=blob(b"plain public source")
                payload=b"plain public source"
                label="blobs/"+expected
                if invalid=="../bad": label="../bad"
                elif invalid=="unexpected-oid": label="blobs/"+"a"*40
                elif invalid=="crx": payload=b"Cr24extension"
                elif invalid=="content": payload=b"different"
                with tarfile.open(archive,"w:gz") as t:
                    info=tarfile.TarInfo(label)
                    info.mode=0o644
                    if invalid=="symlink":
                        info.type=tarfile.SYMTYPE
                        info.linkname="/etc/passwd"
                    else:
                        info.size=len(payload)
                    t.addfile(info,io.BytesIO(payload))
                metadata={"name":archive.name,"bytes":archive.stat().st_size,"sha256":a.digest(archive.read_bytes()),
                          "packed_blobs":[expected],"packed_blob_count":1,"crx_magic_excluded":[]}
                status={}
                if invalid:
                    with self.assertRaises(ValueError):
                        a.publish_archive(archive,dest,{expected},metadata,status)
                    self.assertEqual(list(dest.iterdir()),[])
                else:
                    a.publish_archive(archive,dest,{expected},metadata,status)
                    self.assertEqual((dest/archive.name).read_bytes(),archive.read_bytes())
                    self.assertEqual(status["preimage_archive"]["exact_blobs"],1)

    def test_exact_blob_batch_uses_real_git_no_worktree_or_unrequested_blob(self):
        # Only disposable local fixture serving Git protocol v2. The production
        # audit constructor hard-codes HTTPS only and cannot use file://.
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);origin=p/"origin";origin.mkdir()
            x=a.Audit(p,os.environ)
            x.online={**x.online,"GIT_ALLOW_PROTOCOL":"file"}
            x.git(origin,"init","-q")
            x.git(origin,"config","uploadpack.allowFilter","true")
            x.git(origin,"config","uploadpack.allowAnySHA1InWant","true")
            (origin/"requested").write_bytes(b"wanted")
            (origin/"not-requested").write_bytes(b"not wanted")
            x.git(origin,"add","-A")
            x.git(origin,"-c","user.email=test@example.test","-c","user.name=Test","commit","-qm","fixture")
            rev=x.rev(origin,"HEAD")
            url=origin.as_uri()
            target=p/"target"
            x.prep_repo(target,url)
            x.git(target,"fetch","--depth=1","--filter=blob:none","origin",rev+":refs/sanb/audit/"+rev,network=True)
            good=blob(b"wanted");bad=blob(b"not wanted")
            self.assertEqual(x.tree_blobs(target,rev,["requested"]),{good})
            self.assertEqual(x.present(target,{good,bad}),set())
            self.assertEqual(replay.in_git({good,bad},target),set())
            self.assertEqual(x.wanted(target,{good}),set())
            self.assertEqual(x.present(target,{good,bad}),{good})
            self.assertEqual(replay.in_git({good,bad},target),{good})
            self.assertEqual(sorted(y.name for y in target.iterdir()),[".git"])

    def test_availability_never_queries_missing_promisor_input(self):
        good, missing, extra, tree = (c*40 for c in "abcd")
        supplied = (
            f"{good} blob 5\n{tree} tree 20\n{extra} blob 8\n"
        ).encode()
        def check_args(args):
            self.assertIn("--batch-all-objects", args)
            self.assertIn("--batch-check=%(objectname) %(objecttype) %(objectsize)", args)
            self.assertFalse(any(missing in str(arg) for arg in args))
        def wrapper_git(repo,*args,**kwargs):
            check_args(args)
            # The failing CircleCI style submitted absent OIDs via stdin.
            self.assertNotIn("data", kwargs)
            return subprocess.CompletedProcess(args,0,supplied,b"")
        def replay_git(args,**kwargs):
            check_args(args)
            self.assertNotIn("input",kwargs)
            self.assertEqual(kwargs["env"]["GIT_ALLOW_PROTOCOL"],"")
            return subprocess.CompletedProcess(args,0,supplied,b"")
        with mock.patch.object(a.Audit,"git",side_effect=wrapper_git):
            self.assertEqual(a.Audit(ROOT,{}).present(ROOT,{good,missing,tree}),{good})
        with mock.patch.object(replay.subprocess,"run",side_effect=replay_git):
            self.assertEqual(replay.in_git({good,missing,tree},ROOT),{good})

    def test_bare_patch_extraction_never_reads_root_metadata_or_crx(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); origin=p/"origin"; origin.mkdir()
            x=a.Audit(p,os.environ)
            x.online={**x.online,"GIT_ALLOW_PROTOCOL":"file"}
            x.git(origin,"init","-q")
            x.git(origin,"config","uploadpack.allowFilter","true")
            x.git(origin,"config","uploadpack.allowAnySHA1InWant","true")
            raw=b"canonical patch bytes\n"; ignore=b"known-ignore-object\n"; crx=b"Cr24known-excluded-bundle"
            (origin/"patches").mkdir()
            (origin/"patches/0000001.patch").write_bytes(raw)
            (origin/".gitignore").write_bytes(ignore)
            (origin/"bundled.crx").write_bytes(crx)
            x.git(origin,"add","-A")
            identity=("-c","user.email=test@example.test","-c","user.name=Test")
            x.git(origin,*identity,"commit","-qm","fixture")
            x.git(origin,*identity,"tag","-am","bare fixture","v2.0.7")
            pins=dict(BARE_URL=origin.as_uri(),BARE_TAG=x.rev(origin,a.TAG),
                      BARE_COMMIT=x.rev(origin,"HEAD"),BARE_TREE=x.rev(origin,"HEAD^{tree}"))
            original=x.git
            def no_checkout(repo,*args,**kwargs):
                # Optionally absent root metadata must never be accessed by any
                # checkout machinery, even if a particular Git version permits it.
                self.assertFalse({"checkout","sparse-checkout","read-tree"}&set(args))
                return original(repo,*args,**kwargs)
            remote=p/"source.git"; fixture=p/"patch-fixture"
            with mock.patch.multiple(a,**pins), mock.patch.object(x,"git",side_effect=no_checkout):
                x.bare(remote,fixture,[{"id":"0000001","sha256":a.digest(raw)}])
            self.assertEqual(x.git(remote,"rev-parse","--is-bare-repository").stdout,b"true\n")
            self.assertEqual(x.present(remote,{blob(raw),blob(ignore),blob(crx)}),{blob(raw)})
            self.assertEqual(sorted(f.name for f in fixture.iterdir()),["0000001.patch"])
            self.assertEqual((fixture/"0000001.patch").read_bytes(),raw)
            self.assertFalse((remote/"index").exists())
            self.assertFalse((remote/".git").exists())

    def test_wrong_branch_fail_does_not_call_remote(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            with mock.patch.object(a.Audit,"prep_repo",side_effect=AssertionError("network")):
                self.assertEqual(a.main(p,{"CIRCLE_BRANCH":"raw-sandium/official158"}),1)
            r=json.loads((p/".sanb-source-audit-artifacts/status.json").read_text())
            self.assertEqual(r["stage"],"preflight")
            self.assertFalse(r["apk_produced"] or r["build_admission"] or r["checkpoint_saved"])
