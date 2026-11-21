#!/usr/bin/env python3
"""Bounded source-only SanB audit: retrieve exact Git preimages; never build."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time

BRANCH = "sanb/official158"
BARE_URL = "https://github.com/BareBrowser/bare-browser.git"
CHROMIUM_URL = "https://github.com/chromium/chromium.git"
TAG = "refs/tags/v2.0.7"
BARE_TAG = "fd861600035a4d34fb54c3f9e96f7a88af875f88"
BARE_COMMIT = "e4265e92c914765822bf31b6bb12afcb70bf7a77"
BARE_TREE = "3cd8b22de30883a9e6211ac9e02dcc9f9bddbee5"
M158 = "52bdd21723d5db0c9ab11716d38feac74828cf84"
M157 = "4b3d0dabb8250b6f152d2d85d79e7706e309d087"
TREES = {M158: "f4f4494c6b24bd614e3e13a966d17f27dd52e436",
         M157: "1390557da6bf6cb630528eac294f338b887ad81a"}
INVENTORY = "sanb-source/canonical-inventory.json"
INVENTORY_SHA = "ef39400e83b8f28a3f94627a4e5e72b58a8b4fd7daa89d61b07bffe08b322bb7"
REPLAY = "tools/sanb_bulk_context.py"
REPLAY_HELPER = "tools/sanb_replay_groups.py"
DRIVER_SHA = "658b280f84389e24346456da7e2b5204c57e987815bd36515fe2889e1577aa62"
HELPER_SHA = "a1b4b22be6ca02f24cd0c6fdb90e100857b233b39fa36849f69d77182a3e39d7"
OID = re.compile(r"[0-9a-f]{40}")
SHA = re.compile(r"[0-9a-f]{64}")
AUDIT_SECONDS = 21 * 60
OUTPUT_LIMIT = 64 * 2**20
REPORT_LIMIT = 5 * 2**20
PACK_LIMIT = 56 * 2**20
MIN_FREE = 2 * 2**30


def file(root, rel):
    p = root / rel
    if p.is_symlink() or not p.is_file() or p.resolve() != root.resolve() / rel:
        raise ValueError("Unsafe or missing regular audit input " + str(rel))
    return p


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validated_path(value):
    if not isinstance(value, str) or not value or len(value) > 350 or not value.isascii():
        raise ValueError("Unrecognized canonical donor path")
    p = PurePosixPath(value)
    if (p.is_absolute() or str(p) != value or any(x.lower() in {".git", ".."} for x in p.parts)
            or any(c in value for c in "\r\n\0\t\\") or value.startswith(":")):
        raise ValueError("Unsafe canonical donor path")
    return value


def read_inventory(p):
    raw = p.read_bytes()
    if digest(raw) != INVENTORY_SHA:
        raise ValueError("Unexpected canonical Bare patch inventory SHA256")
    value = json.loads(raw)
    rows = value.get("chronology", []) if isinstance(value, dict) else []
    if value.get("bare") != BARE_COMMIT or len(rows) != 346:
        raise ValueError("Unexpected canonical Bare donor identity or patch count")
    seen, paths = set(), set()
    previous = ""
    for row in rows:
        key = row["id"]
        if (not re.fullmatch(r"[0-9]{7}", key) or key in seen or key <= previous
                or not SHA.fullmatch(row["sha256"]) or not row.get("classification")):
            raise ValueError("Unexpected canonical chronology entry")
        previous = key
        seen.add(key)
        paths.update(validated_path(x) for x in row["paths"])
    if not 1 <= len(paths) <= 2000:
        raise ValueError("Unbounded source-audit path set")
    return rows, sorted(paths)


def env_for(environ, *, network):
    allow = {"HOME", "PATH", "LANG", "LC_ALL", "TMPDIR", "USER"}
    env = {k: v for k, v in environ.items() if k in allow}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_TERMINAL_PROMPT": "0", "GIT_ATTR_NOSYSTEM": "1",
                "GIT_ALLOW_PROTOCOL": "https" if network else "",
                "GIT_LFS_SKIP_SMUDGE": "1", "PYTHONDONTWRITEBYTECODE": "1",
                "GIT_NO_REPLACE_OBJECTS": "1", "GIT_NO_LAZY_FETCH": "1"})
    return env


def command(args, *, cwd, env, deadline, cap, data=None, checked=True):
    left = min(cap, int(deadline - time.monotonic()))
    if left < 1:
        raise TimeoutError("Source-audit overall budget expired")
    p = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                         start_new_session=True)
    try:
        out, err = p.communicate(input=data, timeout=left)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        os.killpg(p.pid, signal.SIGKILL)
        p.wait(timeout=10)
        raise TimeoutError(f"Source audit exceeded {left}s running {Path(args[0]).name}") from None
    if checked and p.returncode:
        raise ValueError(f"{Path(args[0]).name} {args[1]} failed ({p.returncode}): " +
                         err[-1800:].decode(errors="replace").strip())
    return subprocess.CompletedProcess(args, p.returncode, out, err)


class Audit:
    def __init__(self, root, env):
        self.root = root
        self.online = env_for(env, network=True)
        self.offline = env_for(env, network=False)
        self.deadline = time.monotonic() + AUDIT_SECONDS

    def git(self, work, *args, data=None, network=False, cap=30, checked=True, extra_env=None):
        env = self.online if network else self.offline
        if extra_env:
            env = env | extra_env
        cmd = ["git", "-c", "core.hooksPath=/dev/null", "-c", "protocol.version=2",
               "-c", "http.followRedirects=false", "-c", "http.lowSpeedLimit=1024",
               "-c", "http.lowSpeedTime=35", *args]
        return command(cmd, cwd=work, env=env, deadline=self.deadline, data=data,
                       cap=cap, checked=checked)

    def verify_transport(self, url):
        out = self.git(self.root, "ls-remote", "--symref", url, "HEAD", cap=45, network=True,
                       extra_env={"GIT_TRACE_PACKET": "1"})
        if not any(b"fetch=" in line and re.search(rb"\bfilter\b", line)
                   for line in out.stderr.splitlines()):
            raise ValueError("Public upstream did not advertise object filtering; refusing full fetch")

    def prep_repo(self, repo, url):
        repo.mkdir()
        self.verify_transport(url)
        self.git(repo, "init", "-q")
        self.git(repo, "remote", "add", "origin", url)
        self.git(repo, "config", "remote.origin.promisor", "true")
        self.git(repo, "config", "remote.origin.partialclonefilter", "blob:none")
        self.git(repo, "config", "core.hooksPath", "/dev/null")

    def rev(self, repo, expr):
        out = self.git(repo, "rev-parse", "--verify", expr).stdout.decode().strip()
        if not OID.fullmatch(out):
            raise ValueError("Missing exact Git object identity")
        return out

    def present(self, repo, ids):
        if not ids:
            return set()
        # Do not directly query a missing promisor OID: some Git versions
        # abort even with lazy fetch disabled. Enumerate local objects only.
        res = self.git(repo, "cat-file", "--batch-all-objects", "--unordered",
                       "--batch-check=%(objectname) %(objecttype) %(objectsize)", cap=55)
        return ids & {line.split()[0].decode() for line in res.stdout.splitlines()
                      if re.fullmatch(rb"[a-f0-9]{40} blob [0-9]+", line)}

    def tree_blobs(self, repo, rev, paths):
        all_ids = set()
        # Only these names, not a Chromium worktree. Keep process argv bounded.
        for offset in range(0, len(paths), 200):
            names = paths[offset:offset+200]
            match = set(names)
            out = self.git(repo, "ls-tree", "-r", "-z", rev, "--", *names, cap=40).stdout
            for entry in out.split(b"\0"):
                if not entry:
                    continue
                left, right = entry.split(b"\t", 1)
                mode, kind, oid = left.decode().split()
                if right.decode() not in match:
                    raise ValueError("Unexpected tree path outside exact inventory")
                if mode in ("100644", "100755") and kind == "blob" and OID.fullmatch(oid):
                    all_ids.add(oid)
        return all_ids

    def wanted(self, repo, ids):
        missing = sorted(ids - self.present(repo, ids))
        for n in range(0, len(missing), 256):
            batch = missing[n:n+256]
            print(f"SANB_AUDIT hydrate {n+len(batch)}/{len(missing)} exact blob IDs", flush=True)
            # A commit/tag ref is already present after the tree fetch, but it
            # does not imply that its blobs are here. Do not negotiate it as a have.
            self.git(repo, "-c", "fetch.negotiationAlgorithm=noop",
                     "fetch", "--no-tags", "--no-recurse-submodules", "--no-write-fetch-head",
                     "--no-auto-maintenance", "--filter=blob:none", "--stdin", "origin",
                     data="".join(h+"\n" for h in batch).encode(), network=True, cap=80,
                     checked=False)
            # If a batch is rejected, do not substitute a full checkout. Preserve
            # the still-unread set for the chronology report.
        return ids - self.present(repo, ids)

    def bare(self, repo, rows):
        self.prep_repo(repo, BARE_URL)
        self.git(repo, "fetch", "--depth=1", "--no-tags", "--no-recurse-submodules",
                 "--filter=blob:none", "origin", f"{TAG}:{TAG}", network=True, cap=120)
        for expr, sha in ((TAG, BARE_TAG), (TAG+"^{commit}", BARE_COMMIT),
                          (TAG+"^{tree}", BARE_TREE)):
            if self.rev(repo, expr) != sha:
                raise ValueError("Bare v2.0.7 tag/commit/tree is not the exact reviewed object")
        patch_paths = [f"patches/{row['id']}.patch" for row in rows]
        ids = self.tree_blobs(repo, BARE_COMMIT, patch_paths)
        if len(ids) != len(patch_paths) or self.wanted(repo, ids):
            raise ValueError("Did not hydrate exact canonical Bare patch objects")
        # Only checked-in patch files and no donor hook/script are materialized.
        config = "".join("/"+name+"\n" for name in patch_paths).encode()
        self.git(repo, "sparse-checkout", "set", "--no-cone", "--stdin", data=config)
        self.git(repo, "checkout", "--no-recurse-submodules", "--detach", BARE_COMMIT, cap=55)
        if self.rev(repo, "HEAD") != BARE_COMMIT or self.git(repo, "status", "--porcelain").stdout:
            raise ValueError("Bare sparse archive is not exactly pinned and clean")
        for row, name in zip(rows, patch_paths):
            if digest(file(repo, name).read_bytes()) != row["sha256"]:
                raise ValueError("Canonical Bare patch bytes differ from inventory")

    def chromium(self, repo, paths):
        self.prep_repo(repo, CHROMIUM_URL)
        refs = [pin + ":refs/sanb/audit/" + pin for pin in TREES]
        self.git(repo, "fetch", "--depth=1", "--no-tags", "--no-recurse-submodules",
                 "--filter=blob:none", "origin", *refs, network=True, cap=240)
        for pin, tree in TREES.items():
            if self.rev(repo, pin+"^{tree}") != tree:
                raise ValueError("Chromium pin does not identify the expected exact tree")
        ids = set().union(*(self.tree_blobs(repo, pin, paths) for pin in TREES))
        if not 1 <= len(ids) <= 5000:
            raise ValueError("Malformed exact Chromium first-preimage object set")
        return ids, self.wanted(repo, ids)


def safe_report(path):
    if path.stat().st_size > REPORT_LIMIT:
        raise ValueError("Chronology report exceeds compact artifact budget")
    data = json.loads(path.read_text())
    if (data.get("status") != "contextual-evidence-only"
            or data.get("canonical_patch_count") != 346 or data.get("target") != M158
            or data.get("bare") != BARE_COMMIT or data.get("donor_base") != M157):
        raise ValueError("Replay result is not unchanged source-only evidence")
    return data


def publish_archive(source, output, expected_ids, metadata, status):
    if source.is_symlink() or not source.is_file():
        raise ValueError("Unexpected preimage archive file type")
    if (not isinstance(metadata, dict) or metadata.get("name") != source.name
            or metadata.get("bytes") != source.stat().st_size):
        raise ValueError("Preimage pack receipt differs from output")
    if source.stat().st_size > PACK_LIMIT:
        status["preimage_archive"] = "omitted-compressed-output-cap"
        return
    with source.open("rb") as stream:
        archive_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    if metadata.get("sha256") != archive_sha:
        raise ValueError("Preimage archive SHA256 differs from receipt")
    members = set()
    size = 0
    with tarfile.open(source, mode="r|gz") as archive:
        for member in archive:
            match = re.fullmatch(r"blobs/([0-9a-f]{40})", member.name)
            if (member.type != tarfile.REGTYPE or member.mode != 0o644
                    or match is None or member.size > 32 * 2**20
                    or member.size < 0):
                raise ValueError("Untrusted or off-catalog preimage archive member")
            oid = match.group(1)
            if oid in members or oid not in expected_ids:
                raise ValueError("Duplicate or unrequested preimage archive member")
            size += member.size
            if size > 256 * 2**20:
                raise ValueError("Unbounded expanded preimage archive")
            m = archive.extractfile(member)  # Validate only; never extract onto disk.
            h = hashlib.sha1(f"blob {member.size}\0".encode(), usedforsecurity=False)
            prefix = m.read(4)
            if prefix == b"Cr24":
                raise ValueError("Bundled extension object cannot be a diagnostic artifact")
            h.update(prefix)
            for chunk in iter(lambda: m.read(65536), b""):
                h.update(chunk)
            if h.hexdigest() != oid:
                raise ValueError("Preimage blob bytes do not match their pinned object identity")
            members.add(oid)
    excluded, packed = metadata.get("crx_magic_excluded"), metadata.get("packed_blobs")
    if (not isinstance(excluded, list) or not isinstance(packed, list)
            or any(not isinstance(h, str) or not OID.fullmatch(h) for h in excluded+packed)
            or len(set(excluded)) != len(excluded) or len(set(packed)) != len(packed)
            or members != set(packed) or len(members) != metadata.get("packed_blob_count")
            or members.intersection(excluded) or members.union(excluded) != expected_ids):
        raise ValueError("Preimage archive inventory coverage differs from audit receipt")
    if source.stat().st_size + sum(p.stat().st_size for p in output.iterdir()) > OUTPUT_LIMIT:
        status["preimage_archive"] = "omitted-total-output-cap"
        return
    shutil.copyfile(source, output/source.name)
    status["preimage_archive"]={"sha256":archive_sha,"bytes":source.stat().st_size,
                                "exact_blobs":len(members),"excluded_crx":len(excluded)}


def main(root, environ):
    output = root/".sanb-source-audit-artifacts"
    output.mkdir(mode=0o700)
    status = {"schema":1, "mode":"source-audit", "workflow":"SanB", "apk_produced":False,
              "build_admission":False, "checkpoint_saved":False, "compiler_started":False}
    stage = "preflight"
    start = time.monotonic()
    try:
        a = Audit(root, environ)
        if environ.get("CIRCLE_BRANCH") != BRANCH:
            raise ValueError("Wrong SanB diagnostic branch")
        status["git_version"] = a.git(root, "--version").stdout.decode().strip()
        status["checkout"] = a.rev(root,"HEAD")
        if environ.get("CIRCLE_SHA1") != status["checkout"]:
            raise ValueError("SanB diagnostic invoked on wrong checkout commit")
        if shutil.disk_usage(root).free < MIN_FREE:
            raise ValueError("Insufficient free disk for target-only source audit")
        inventory = file(root, INVENTORY)
        rows, paths = read_inventory(inventory)
        script=file(root,REPLAY); helper=file(root,REPLAY_HELPER)
        if digest(script.read_bytes()) != DRIVER_SHA or digest(helper.read_bytes()) != HELPER_SHA:
            raise ValueError("SanB exact reviewed chronology tools differ")
        a.git(root,"ls-files","--error-unmatch","--",INVENTORY,REPLAY,REPLAY_HELPER)
        if a.git(root,"diff","--exit-code","HEAD","--",INVENTORY,REPLAY,REPLAY_HELPER).stdout:
            raise ValueError("Audit runner/inventory drifted from verified checkout")
        status.update(inventory_sha256=digest(inventory.read_bytes()),
                      driver_sha256=digest(script.read_bytes()), helper_sha256=digest(helper.read_bytes()))
        work=root/".sanb-source-audit-work"
        work.mkdir(mode=0o700)
        stage="bare-filtered-tag"
        print("SANB_AUDIT prepare exact Bare tag (patch files only)",flush=True)
        bare=work/"bare"; chromium=work/"chromium"
        a.bare(bare,rows)
        stage="chromium-exact-preimages"
        print("SANB_AUDIT prepare exact M158 and provenance M157 Chromium trees",flush=True)
        total, missing=a.chromium(chromium,paths)
        status.update(queried_objects=len(total), missing_objects=len(missing))
        (output/"first-preimages.json").write_text(json.dumps(
            {"requested_objects":sorted(total),"missing_objects":sorted(missing),
             "chromium_trees":TREES,"bare_tree":BARE_TREE},sort_keys=True)+"\n")
        stage="offline-chronology-replay"
        print(f"SANB_AUDIT replay exact chronology offline missing={len(missing)}",flush=True)
        reports=work/"reports"
        p=command([sys.executable,"-u",str(script),"--output",str(reports),
                   "--chromium-repo",str(chromium),"--bare-repo",str(bare),
                   "--inventory",str(inventory),"--require-all-preimages","--pack-preimages"],
                  cwd=root,env=a.offline,deadline=a.deadline,cap=420,checked=False)
        if p.returncode not in (0,3):
            raise ValueError("Chronology replay could not emit report: "+p.stderr[-1600:].decode(errors="replace"))
        report=file(reports,"bulk-context.json")
        data=safe_report(report)
        if (data.get("unique_upstream_blobs_both_pins") != len(total)
                or data.get("readable_unique_upstream_blobs_both_pins") != len(total - missing)
                or data.get("unread_unique_upstream_blobs_both_pins") != len(missing)
                or (p.returncode == 0) != (not missing)):
            raise ValueError("Chronology report disagrees with verified exact blob availability")
        shutil.copyfile(report,output/report.name)
        status.update(replay_sha256=digest(report.read_bytes()), replay_returncode=p.returncode,
                      statuses=data["target_m158"]["status_counts"])
        package=file(reports,"sanb-pinned-preimages.tar.gz")
        publish_archive(package, output, total-missing, data.get("preimages_pack"), status)
        status["result"] = "complete-context-audit-not-build-admitted" if p.returncode==0 else "partial-preimages"
        return p.returncode
    except (ValueError, OSError, TypeError, KeyError, TimeoutError, tarfile.TarError) as e:
        status.update(result="failed",stage=stage,error=str(e))
        print(f"SANB_AUDIT_FAILED stage={stage}: {e}",file=sys.stderr,flush=True)
        return 1
    finally:
        status["elapsed_seconds"]=int(time.monotonic()-start)
        (output/"status.json").write_text(json.dumps(status,indent=2,sort_keys=True)+"\n")
        print("SANB_SOURCE_AUDIT_ONLY no APK or build-admission receipt",flush=True)


if __name__ == "__main__":
    sys.exit(main(Path.cwd(),os.environ))
