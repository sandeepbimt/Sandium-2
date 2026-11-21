#!/usr/bin/env python3
"""One bounded SanB worker; no restore, checkpoint saving, signer or key paths."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import zipfile

BRANCH = "sanb/official158"
BARE = "e4265e92c914765822bf31b6bb12afcb70bf7a77"
CHROMIUM = "52bdd21723d5db0c9ab11716d38feac74828cf84"
VERSION = "158.0.8127.42"
DEPOT = "fed8b43f48c4f4c2ac0c34aafbf0ec07a4e600cb"
PACKAGE = "io.github.sandeepbimt.sanb"
LABEL = "SanB"
TARGET = "chrome_public_apk"
OUT = "out/SanB-arm64"
LABEL_PACKAGE_ACTION = "//chrome/android:chrome_public_apk__create"
UBLOCK = re.compile(r"u[-_]?block(?:[-_]?origin)?|cjpalhdlnbpafiamejdnhcphjbkeiagm", re.I)
V1_SIG = re.compile(r"META-INF/(?:[^/]+\.(?:SF|RSA|DSA|EC)|SIG-[^/]+)", re.I)
SIG_BLOCK = b"APK Sig Block 42"
MIN_GIB = 130
WORKER_SECONDS = 55 * 60
RESERVE_SECONDS = 150
DISALLOWED_ENV = {
    "RAWS_TEST_KEYSTORE_B64", "RAWS_KEYSTORE_PASSWORD", "RAWS_KEY_PASSWORD",
    "RAWS_TEST_SIGNER_PIN_SHA256", "SANB_KEYSTORE_B64", "SANB_KEYSTORE_PASSWORD",
    "SANB_KEY_PASSWORD", "SANB_SIGNER_PIN_SHA256",
}


def deny_preexisting_keys(env):
    if DISALLOWED_ENV.intersection(env):
        raise ValueError("Signing credentials must not be present in this unsigned lane")


def subprocess_env(env, depot=None):
    """Forward only required public environment fields, never other project tokens."""
    allowed = {"HOME", "PATH", "LANG", "LC_ALL", "TMPDIR", "USER", "SHELL"}
    public = {k: v for k, v in env.items() if k in allowed}
    if depot is not None:
        public["PATH"] = str(depot) + os.pathsep + public.get("PATH", os.defpath)
    public.update({"DEPOT_TOOLS_UPDATE": "0", "PYTHONDONTWRITEBYTECODE": "1"})
    return public


def regular(p):
    if p.is_symlink() or not p.is_file():
        raise ValueError(f"Expected regular file: {p.name}")
    return p


def inside(root, relative):
    item = root / relative
    if item.resolve() != root.resolve() / relative or item.is_symlink():
        raise ValueError("Unexpected symlink in SanB worker path")
    return item


def sha(p):
    with regular(p).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def read_current(root, env):
    if env.get("CIRCLE_BRANCH") != BRANCH:
        raise ValueError("Unexpected SanB branch")
    value = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, timeout=10,
                                    env=subprocess_env(env)).strip()
    if not re.fullmatch(r"[a-f0-9]{40}", value) or env.get("CIRCLE_SHA1") != value:
        raise ValueError("CircleCI checkout does not match the exact requested SanB commit")
    return value


def verify_source_receipt(data):
    expected = {
        "schema": 1, "bare": BARE, "chromium": CHROMIUM, "version": VERSION,
        "android_desktop": True, "embedded_ublock": False,
    }
    if (not isinstance(data, dict) or any(data.get(k) != v or type(data.get(k)) is not type(v)
                                      for k, v in expected.items())):
        raise ValueError("SanB source adapter did not prove exact Bare Desktop M158 without uBlock")
    if not isinstance(data.get("patch_sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", data["patch_sha256"]):
        raise ValueError("SanB source adapter has no exact patch or composition digest")
    return data


def actions_left(epoch):
    return int(epoch + WORKER_SECONDS - time.time() - RESERVE_SECONDS)


def run(command, *, cwd, env, deadline, log, phase, cap=None):
    """Bound every process group to the shared worker deadline, including gclient."""
    remaining = actions_left(deadline)
    if cap is not None:
        remaining = min(remaining, cap)
    if remaining < 1:
        raise TimeoutError(f"No worker time left for {phase}")
    start = time.monotonic()
    print(f"SANB_BEGIN phase={phase} seconds_left={remaining}", flush=True)
    with log.open("wb") as stream:
        p = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                             stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline_secs = start + remaining
            while p.poll() is None:
                secs = deadline_secs - time.monotonic()
                if secs <= 0:
                    raise subprocess.TimeoutExpired(command, remaining)
                try:
                    p.wait(timeout=min(30, secs))
                except subprocess.TimeoutExpired:
                    print(f"SANB_HEARTBEAT phase={phase} elapsed={int(time.monotonic()-start)} "
                          f"log_bytes={log.stat().st_size}", flush=True)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            os.killpg(p.pid, signal.SIGTERM)
            try:
                p.wait(timeout=12)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait(timeout=5)
            raise TimeoutError(f"SanB timed out during {phase}") from None
    print(f"SANB_END phase={phase} rc={p.returncode} time={int(time.monotonic()-start)}", flush=True)
    if p.returncode:
        # Full build logs are workflow-local, not public. Show only a bounded tail in CI.
        print(log.read_bytes()[-12000:].decode(errors="replace"), flush=True)
        raise ValueError(f"SanB {phase} failed (exit {p.returncode})")


def checked(command, cwd, env, seconds=45):
    return subprocess.check_output(command, cwd=cwd, env=env, text=True, timeout=seconds,
                                   stderr=subprocess.STDOUT)


def verify_build_args(text):
    required = {
        "target_os": '"android"', "target_cpu": '"arm64"',
        "is_debug": "false", "is_component_build": "false", "is_official_build": "true",
        "is_desktop_android": "true", "use_remoteexec": "false", "use_reclient": "false",
        "chrome_public_manifest_package": f'"{PACKAGE}"', "sanb_unsigned_apk": "true",
    }
    for key, expected in required.items():
        observed = re.findall(rf"^\s*{key}\s*=\s*([^\n#]+?)\s*$", text, re.M)
        if observed != [expected]:
            raise ValueError(f"Unexpected or duplicate SanB GN option: {key}")


def verify_apk_graph(src, out, gn, env):
    target = "./" + out.relative_to(src).as_posix()
    def query(lab, field, *args):
        return checked([gn, "desc", target, lab, field, *args], src, env).splitlines()
    args, inputs, outputs = (query(LABEL_PACKAGE_ACTION, field) for field in ("args","inputs","outputs"))
    deps = query("//chrome/android:chrome_public_apk", "deps", "--all")
    if (not any("--output-apk=" in x and x.rstrip().endswith("/ChromePublic.apk") for x in args)
            or not any(x.strip().endswith("/ChromePublic.apk") for x in outputs)
            or any(re.search(r"--key-(?:path|name|passwd)(?:\s|$|=)", x) for x in args)
            or any(re.search(r"\.(?:jks|keystore|p12|pfx)\s*$", x, re.I) for x in inputs)
            or any(x.rstrip().endswith(".idsig") for x in outputs)
            or any(UBLOCK.search(x) for x in args + inputs + outputs + deps)):
        raise ValueError("SanB GN packager has a signing or bundled-uBlock dependency")


def verify_zip(apk):
    regular(apk)
    if apk.with_name(apk.name + ".idsig").exists():
        raise ValueError("SanB output has a signature sidecar")
    with zipfile.ZipFile(apk) as archive:
        files = archive.namelist()
        if "AndroidManifest.xml" not in files or len(files) != len(set(files)) or archive.testzip():
            raise ValueError("SanB unsigned APK failed ZIP integrity")
        if any(V1_SIG.fullmatch(n) or UBLOCK.search(n) for n in files):
            raise ValueError("SanB output includes a signature or bundled uBlock file")
        libraries = [n for n in files
                     if n.startswith("lib/") and n.count("/") >= 2 and n.endswith(".so")]
        abis = {n.split("/")[1] for n in libraries}
        if abis != {"arm64-v8a"} or "lib/arm64-v8a/libchrome.so" not in files:
            raise ValueError("SanB APK does not contain ARM64-only libchrome.so")
        for name in libraries:
            with archive.open(name) as lib:
                elf = lib.read(20)
            if elf[:6] != b"\x7fELF\x02\x01" or elf[18:20] != b"\xb7\x00":
                raise ValueError("SanB native library is not ELF64 AArch64")
        if archive.start_dir >= len(SIG_BLOCK):
            with apk.open("rb") as f:
                f.seek(archive.start_dir - len(SIG_BLOCK))
                if f.read(len(SIG_BLOCK)) == SIG_BLOCK:
                    raise ValueError("SanB output has a v2/v3 APK signing block")


def verify_badging(desc):
    if (re.findall(r"^package: name='([^']+)'", desc, re.M) != [PACKAGE]
            or re.findall(r"^application-label:'([^']+)'$", desc, re.M) != [LABEL]
            or re.search(r"^application-debuggable\b", desc, re.M)
            or re.search(r"^native-code:\s*'arm64-v8a'\s*$", desc, re.M) is None):
        raise ValueError("Unexpected SanB release package, label or ABI")


def status_write(folder, status):
    (folder / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")


def main(mode, root, environ):
    folder = inside(root, ".sanb-artifacts")
    if not folder.is_dir():
        raise ValueError("SanB artifact directory was not initialized")
    epoch = float(regular(folder / "epoch").read_text())
    if not 0 <= time.time() - epoch < WORKER_SECONDS:
        raise ValueError("Invalid SanB worker timestamp")
    status = {"schema": 1, "workflow": "SanB", "branch": BRANCH, "mode": mode,
              "chromium": CHROMIUM, "expected_bare": BARE, "apk_produced": False,
              "signed": False, "checkpoint_saved": False}
    stage = "admission"
    try:
        deny_preexisting_keys(environ)
        status["commit"] = read_current(root, environ)
        w = inside(root, ".sanb-work")
        if w.exists():
            raise ValueError("Refusing pre-existing SanB worker workspace")
        env = subprocess_env(environ)
        adapter = regular(inside(root, "tools/sanb_source.py"))
        args_path = regular(inside(root, "ci/sanb-args.gn"))
        verify_build_args(args_path.read_text())
        disk_gib = shutil.disk_usage(root).free // 2**30
        status.update(free_gib=disk_gib, cpu=os.cpu_count())
        stage = "static-source-proof"
        run([sys.executable, str(adapter), "verify", "--receipt", str(folder/"source-plan.json")],
            cwd=root, env=env, deadline=epoch, log=folder/"source-plan.log", phase=stage)
        plan = verify_source_receipt(json.loads(regular(folder/"source-plan.json").read_bytes()))
        status.update(local_source_plan_verified=True, patch_sha256=plan["patch_sha256"])
        if disk_gib < MIN_GIB:
            raise ValueError(f"SanB cold workspace needs at least {MIN_GIB} GiB free; worker reports {disk_gib}")
        if mode == "preflight":
            status.update(result="preflight_passed_no_compile")
            print("SANB_PREFLIGHT_PASS plan_verified=true apk_produced=false", flush=True)
            return 0
        stage = "pinned-source-prepare"
        run([sys.executable, str(adapter), "prepare", "--workspace", str(w),
             "--receipt", str(folder/"source-ready.json")],
            cwd=root, env=env, deadline=epoch, log=folder/"source-ready.log", phase=stage)
        applied = verify_source_receipt(json.loads(regular(folder/"source-ready.json").read_bytes()))
        if applied != plan:
            raise ValueError("SanB prepared source is not the admitted recipe")
        src = inside(w, "src")
        depot = inside(w, "depot_tools")
        env = subprocess_env(environ, depot)
        if checked(["git", "rev-parse", "HEAD"], src, env).strip() != CHROMIUM:
            raise ValueError("Prepared Chromium HEAD differs from exact SanB M158")
        if checked(["git", "rev-parse", "HEAD"], depot, env).strip() != DEPOT:
            raise ValueError("Prepared depot_tools HEAD differs from the exact SanB pin")
        exact_overlay = checked(["git", "write-tree"], src, env).strip()
        checked(["git", "diff", "--exit-code"], src, env)
        stage = "host-toolchain"
        install_deps = str(regular(inside(src, "build/install-build-deps.sh")))
        run([install_deps, "--no-prompt"], cwd=src, env=env, deadline=epoch,
            log=folder/"host-toolchain.log", phase=stage, cap=900)
        stage = "upstream-runhooks"
        gclient = str(regular(inside(depot, "gclient")))
        run([gclient, "runhooks"], cwd=w, env=env, deadline=epoch,
            log=folder/"upstream-runhooks.log", phase=stage, cap=600)
        checked(["git", "diff", "--exit-code"], src, env)
        if (checked(["git", "rev-parse", "HEAD"], src, env).strip() != CHROMIUM
                or checked(["git", "write-tree"], src, env).strip() != exact_overlay):
            raise ValueError("Upstream toolchain hooks modified admitted source")
        manifest_version = regular(inside(src, "chrome/VERSION")).read_text()
        components = dict(line.split("=", 1) for line in manifest_version.splitlines() if "=" in line)
        if ".".join(components.get(k, "") for k in ("MAJOR","MINOR","BUILD","PATCH")) != VERSION:
            raise ValueError("Prepared Chromium VERSION differs from exact SanB M158")
        out = inside(src, OUT)
        if out.exists():
            raise ValueError("Prepared source included foreign or unverified build output")
        known_crx = inside(src, "chrome/browser/resources/bare/ublock_origin.crx")
        if known_crx.exists():
            raise ValueError("Prepared SanB source contains bundled uBlock")
        out.mkdir(parents=True)
        (out / "args.gn").write_bytes(args_path.read_bytes())
        stage = "scoped-unsigned-graph"
        import sanb_unsigned
        overlay = sanb_unsigned.apply(src)
        stage = "gn"
        gn = str(regular(inside(depot, "gn")))
        run([gn, "gen", OUT, "--fail-on-unused-args"], cwd=src, env=env, deadline=epoch,
            log=folder/"gn.log", phase=stage)
        verify_apk_graph(src, out, gn, env)
        sanb_unsigned.verify(overlay)
        # No external build caches or remote executor inputs; fail before any oversized job.
        if actions_left(epoch) < 600:
            raise TimeoutError("Less than 10 minutes left for cold Android compilation; do not launch it")
        stage = "compile"
        ninja = str(regular(inside(depot, "autoninja")))
        run([ninja, "-C", OUT, TARGET], cwd=src, env=env, deadline=epoch,
            log=folder/"compile.log", phase=stage)
        stage = "artifact-validation"
        sanb_unsigned.verify(overlay)
        candidate = regular(inside(out, "apks/ChromePublic.apk"))
        verify_zip(candidate)
        sdk = inside(src, "third_party/android_sdk/public/build-tools/37.0.0")
        zipalign = str(regular(inside(sdk, "zipalign")))
        aapt2 = str(regular(inside(sdk, "aapt2")))
        subprocess.run([zipalign, "-c", "-P", "16", "4", str(candidate)], cwd=src,
                       env=env, check=True, timeout=90, stdout=subprocess.DEVNULL)
        verify_badging(checked([aapt2, "dump", "badging", str(candidate)], src, env, seconds=45))
        output = inside(folder, "SanB-158.0.8127.42-arm64-unsigned.apk")
        temporary = output.with_suffix(".pending")
        shutil.copyfile(candidate, temporary)
        candidate_sha = sha(candidate)
        if sha(temporary) != candidate_sha:
            temporary.unlink(missing_ok=True)
            raise ValueError("SanB copied APK digest changed")
        temporary.rename(output)
        status.update(result="verified_unsigned_apk", apk_produced=True, sha256=candidate_sha,
                      bytes=output.stat().st_size, package=PACKAGE, application_label=LABEL,
                      abi="arm64-v8a", zipalign_16k=True, graph_unsigned=True,
                      installable=False, apk=output.name)
        print("SANB_APK_VERIFIED_UNSIGNED sha256=" + candidate_sha, flush=True)
        return 0
    except (ValueError, OSError, TimeoutError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        (folder / "SanB-158.0.8127.42-arm64-unsigned.pending").unlink(missing_ok=True)
        status.update(result="failed", phase=stage, error=str(exc))
        print(f"SANB_FAILED phase={stage}: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        status["elapsed_seconds"] = int(time.time() - epoch)
        status_write(folder, status)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preflight", "build"), required=True)
    options = parser.parse_args()
    sys.exit(main(options.mode, Path.cwd(), os.environ))
