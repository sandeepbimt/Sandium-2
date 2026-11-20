#!/usr/bin/env python3
"""Prepare the pinned native sources in a NEW, disposable overlay (no CI, no download)."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PINS = json.loads((HERE / 'pins.json').read_text())
BRIDGE = 'components/brave_shields/core/common/adblock'
RUST = 'third_party/rust'
VENDOR = RUST + '/chromium_crates_io/vendor'
GN_CRATE = re.compile(r'//brave/(third_party/rust/[a-zA-Z0-9_]+/v[0-9_]+)(?=[/:"\s])')
VENDOR_DIR = re.compile(r'//brave/(third_party/rust/chromium_crates_io/vendor/[A-Za-z0-9._+-]+)/')


CSSPARSER_GN = RUST + '/cssparser/v0_35/BUILD.gn'
CSSPARSER_GN_SHA256 = '65bb55f5d630acb38fde6436d69a99bf604abfec6ee444138912a1889331cf0a'
CSSPARSER_INACTIVE_029 = (
    '  if (epoch == "0.29") {\n'
    '    build_script_inputs = [ "//brave/' + VENDOR + '/cssparser-v0_29/build/match_byte.rs" ]\n'
    '    build_script_outputs = [ "tokenizer.rs" ]\n'
    '  }\n'
)


def gn_for_selection(path, source):
    # This exact 0.35 crate declares a constant epoch; the generated 0.29
    # branch is unreachable. Change only the scan, never the staged GN source.
    if path == CSSPARSER_GN:
        text = source.decode()
        if (hashlib.sha256(source).hexdigest() != CSSPARSER_GN_SHA256 or
                text.count('  epoch = "0.35"\n') != 1 or
                text.count(CSSPARSER_INACTIVE_029) != 1):
            raise ValueError('unreviewed cssparser-v0_35 BUILD.gn branch')
        return text.replace(CSSPARSER_INACTIVE_029, '', 1)
    return source.decode()


def git(repo, *args):
    # Read the selected objects, never tracked worktree files or replace refs.
    return subprocess.check_output(['git', '--no-replace-objects', '-C', str(repo), *args])


def blob(repo, rev, path):
    return git(repo, 'cat-file', 'blob', f'{rev}:{path}')


def bridge_patch(src):
    if (hashlib.sha1(b'blob ' + str(len(src)).encode() + b'\0' + src).hexdigest()
            != '8d01c30593e0afef3dbe583470b1d60028fba49d'
            or src != (HERE / 'fixture/bridge.BUILD.gn').read_bytes()):
        raise ValueError('unreviewed Brave bridge BUILD.gn; refusing to edit')
    return src.replace(b'  visibility = [\n', b'  visibility = [\n    "//components/sandium_adblock:*",\n', 1)


def select(repo, rev):
    # Extract dependency labels and vendor roots from generated Brave GN, not
    # Cargo's default features. This conservatively includes platform branches.
    todo = [BRIDGE + '/rs/BUILD.gn']; visited = set(); roots = {BRIDGE}
    while todo:
        gn = todo.pop()
        if gn in visited:
            continue
        visited.add(gn)
        text = gn_for_selection(gn, blob(repo, rev, gn))
        for crate in GN_CRATE.findall(text):
            roots.add(crate)
            if crate + '/BUILD.gn' not in visited:
                todo.append(crate + '/BUILD.gn')
        roots.update(VENDOR_DIR.findall(text))
    if VENDOR + '/adblock-v0_13' not in roots:
        raise ValueError('vendored engine not reachable from the selected bridge')
    return sorted(roots)


def prepare(repo, out, rev):
    if out.exists() or out.is_symlink():
        raise ValueError('output must be a new directory')
    roots = select(repo, rev)
    vcs = json.loads(blob(repo, rev, VENDOR + '/adblock-v0_13/.cargo_vcs_info.json'))
    if vcs['git']['sha1'] != PINS['adblock_upstream']:
        raise ValueError('engine identity mismatch')
    crate_gn = blob(repo, rev, RUST + '/adblock/v0_13/BUILD.gn')
    if b'cargo_pkg_version = "0.13.3"' not in crate_gn:
        raise ValueError('engine version mismatch')
    records = git(repo, 'ls-tree', '-rz', rev, '--', *roots, 'LICENSE', RUST + '/chromium_crates_io/Cargo.lock')
    with tempfile.TemporaryDirectory(dir=out.parent) as temp:
        tree = Path(temp) / 'tree'; tree.mkdir()
        inventory = {}; requested = set(roots)
        # Use one cat-file process rather than one Git process per vendor file.
        with subprocess.Popen(['git','--no-replace-objects','-C',str(repo),'cat-file','--batch'],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE) as cat:
            try:
                for row in records.split(b'\0'):
                    if not row: continue
                    meta, raw = row.split(b'\t',1); mode, kind, oid = meta.split()
                    path = raw.decode(); parts = PurePosixPath(path)
                    if (kind != b'blob' or mode not in (b'100644',b'100755') or parts.is_absolute()
                        or '..' in parts.parts or '.git' in parts.parts):
                        raise ValueError('unsafe or unsupported upstream entry: '+path)
                    cat.stdin.write(oid+b'\n'); cat.stdin.flush()
                    got, typ, count = cat.stdout.readline().split()
                    if got != oid or typ != b'blob': raise ValueError('unexpected git response')
                    data=cat.stdout.read(int(count))
                    if len(data)!=int(count) or cat.stdout.read(1)!=b'\n': raise ValueError('truncated blob')
                    if hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=oid.decode():
                        raise ValueError('git blob hash mismatch')
                    if path == BRIDGE+'/BUILD.gn': data = bridge_patch(data)
                    dest = tree/'brave'/path; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)
                    dest.chmod(0o755 if mode == b'100755' else 0o644)
                    inventory['brave/'+path]=hashlib.sha256(data).hexdigest()
            finally:
                cat.stdin.close()
        for root in requested:
            if not (tree/'brave'/root).is_dir(): raise ValueError('missing source root: '+root)
        native = tree/'components/sandium_adblock'; native.mkdir(parents=True)
        for name in ('BUILD.gn','request_matcher.h','request_matcher.cc','standard_merge.h','network_decision.h','subresource_decision.h','subresource_decision.cc','document_subresource_factory.h','document_subresource_factory.cc','engine_smoke.cc'):
            data = (HERE/'native'/name).read_bytes(); (native/name).write_bytes(data)
            (native/name).chmod(0o644)
            inventory['components/sandium_adblock/'+name]=hashlib.sha256(data).hexdigest()
        (tree/'source-receipt.json').write_text(json.dumps({'phase':'engine sources only; not GN or APK evidence',
            'pins':PINS,'source_input':rev,'roots':roots,'sha256':inventory},sort_keys=True,indent=2)+'\n')
        os.rename(tree, out)


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('brave_core',type=Path); p.add_argument('chromium_src',type=Path); p.add_argument('new_output',type=Path); a=p.parse_args()
    out=a.new_output.absolute(); out_parent=out.parent.resolve(strict=True)
    for repo in (a.brave_core,a.chromium_src):
        root=Path(git(repo,'rev-parse','--show-toplevel').decode().strip()).resolve()
        if out_parent==root or root in out_parent.parents: raise ValueError('stage outside both source checkouts')
    if git(a.chromium_src,'rev-parse','HEAD').decode().strip()!=PINS['chromium']:
        raise ValueError('RawS Chromium HEAD mismatch')
    rev=PINS['brave_core']; git(a.brave_core,'cat-file','-e',rev+'^{commit}')
    prepare(a.brave_core,out,rev)
    print(f'Staged native source inputs: {out}; no APK or production feature was enabled.')

if __name__=='__main__':
    try: main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        sys.exit(str(exc))
