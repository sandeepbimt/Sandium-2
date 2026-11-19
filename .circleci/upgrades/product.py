#!/usr/bin/env python3
"""Mode-U product admission. No legacy156 preparation fallback is permitted.

Root is the recipe project, with its owned source at brave-work/src. Exact158
source composition is locally reviewed. Runtime source ownership, fresh official
GN and graph audits remain mandatory before readiness. `plan` grants no receipt.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

RECIPE = Path(__file__).resolve().parents[2]
ORDER = tuple(f'.circleci/experimental-steps/product-overlay-{n}-0.sh' for n in range(24,31))
# Local exact-source composition and reset/rollback passed. This is permission
# to attempt preparation, never a claim that GN or Android compilation passed.
BLOCKERS = ()


def plan(root):
    root = Path(root)
    if root.is_symlink():
        raise ValueError('Symlinked project root')
    root = root.resolve()
    if root != RECIPE.resolve():
        raise ValueError('Product adapter must execute from its own recipe project')
    for relative in ORDER:
        if not (root / relative).is_file():
            raise ValueError('Missing ordered product hook: ' + relative)
    spec = importlib.util.spec_from_file_location('upgrade_product_profile', RECIPE/'.circleci/scripts/upgrade_source_profile.py')
    profile = importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)
    profile.load(RECIPE)
    return dict(schema=1, phase='product-preparing', ready=not BLOCKERS,
                source_root=str(root/'brave-work'), ordered_product_hooks=list(ORDER),
                blockers=list(BLOCKERS), source_sync_claim=False,
                product_ready_claim=False, gn_verified=False, apk_verified=False)


def source_module():
    spec = importlib.util.spec_from_file_location('full_u_product_source', RECIPE/'.circleci/upgrades/source.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def retire_reader(root):
    """Use only the feature-local cleanup, not the frozen156 verifier gate."""
    source_module().verify(Path(root)/'brave-work')
    spec = importlib.util.spec_from_file_location(
        'full_u_retired_reader', RECIPE/'.circleci/scripts/verify-sandium-vanilla-brave.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.retire_reader(Path(root)/'brave-work/src/brave', RECIPE)


def verify_base(root):
    """Read-only intermediate integrity; retain the approved startup overlay."""
    source_module().verify(Path(root)/'brave-work')
    core = Path(root)/'brave-work/src/brave'
    spec = importlib.util.spec_from_file_location(
        'full_u_base_integrity', RECIPE/'.circleci/scripts/verify-sandium-vanilla-brave.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.verify_repo_clean(core, module.BRAVE_VERIFY_PREFIXES, 'brave-core')
    module.verify_reader_removed(core, RECIPE)
    partner = Path(root)/'brave-work/src/chrome/browser/partnercustomizations/java/src/org/chromium/chrome/browser/partnercustomizations/PartnerBrowserCustomizations.java'
    if hashlib.sha256(partner.read_bytes()).hexdigest() != 'fedc000b160d907cdd06bdf741f9f79ab92fb192b2a23d76dfc4a9f83ce5284e':
        raise ValueError('Exact158 reviewed startup postimage required')
    # No legacy reset or GN override removal here: this namespace cannot import
    # old compiled state, and silently resetting this path would undo Morphe.
    return dict(phase='product-preparing', intermediate_integrity=True, build_ready=False)


def admit(root):
    result = plan(root)
    source_module().verify(Path(root)/'brave-work')
    # A later source-compatibility hold still fails before the first source write.
    if BLOCKERS:
        raise ValueError('PRODUCT_158_NOT_ADMITTED: ' + '; '.join(result['blockers']))
    return result


def run(root, argv):
    env = dict(os.environ, CIRCLE_WORKING_DIRECTORY=str(root), DEPOT_TOOLS_UPDATE='0')
    subprocess.run(argv, cwd=root, env=env, check=True)


def python(root, relative, *args):
    run(root, [sys.executable, str(root/relative), *map(str,args)])


def proof_path(root):
    directory = root/'brave-work/.sandium'
    if directory.is_symlink():
        raise ValueError('Symlinked product proof directory')
    return directory/'full-u-product-ready.json'


def graph_hashes(root):
    src = (root/'brave-work/src').resolve()
    out = src/'out/android_Release_arm64'
    result, pending = {}, [out/'args.gn',out/'args_generated.gni']
    while pending:
        path = pending.pop()
        resolved = path.resolve()
        if not resolved.is_relative_to(src) or path.is_symlink():
            raise ValueError('GN argument import escapes owned source')
        name = str(resolved.relative_to(src))
        if name in result:continue
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing regular GN argument input: '+name)
        raw = path.read_bytes();result[name] = hashlib.sha256(raw).hexdigest()
        text = re.sub(r'(?m)#.*$', '', raw.decode())
        expressions = re.findall(r'\bimport\s*\(([^)]*)\)',text)
        for expression in expressions:
            match = re.fullmatch(r'\s*"([^"$]+)"\s*',expression)
            if not match:raise ValueError('Unresolved dynamic GN argument import')
            target = match[1]
            pending.append(src/target[2:] if target.startswith('//') else path.parent/target)
    ninja = out/'build.ninja'
    if ninja.is_symlink() or not ninja.is_file() or not ninja.stat().st_size:
        raise ValueError('Missing regular generated build.ninja')
    result['out/android_Release_arm64/build.ninja'] = hashlib.sha256(ninja.read_bytes()).hexdigest()
    return result


GRAPH_REPORTS = ('removal-native.json','removal-low-six.json','removal-leo.json')


def graph_receipt(root, *, archived=True):
    directory = root/'brave-work/.sandium/product-graph' if archived else root/'brave-apk'
    if directory.is_symlink():raise ValueError('Symlinked graph evidence directory')
    path = directory/'removal-graph-receipt.json'
    if path.is_symlink():raise ValueError('Symlinked graph receipt')
    value = json.loads(path.read_text())
    if value.get('schema') != 1 or value.get('source_revision') != os.environ.get('CIRCLE_SHA1') or not value.get('source_revision'):
        raise ValueError('Stale or missing graph source identity')
    recipe = root/'.circleci/features/removal-recipe.json'
    if value.get('recipe_sha256') != hashlib.sha256(recipe.read_bytes()).hexdigest():
        raise ValueError('Changed removal recipe')
    names = set(GRAPH_REPORTS)
    if set(value.get('reports',{})) != names:
        raise ValueError('Incomplete removal graph audit reports')
    for name, expected in value['reports'].items():
        report = directory/name
        if report.is_symlink():raise ValueError('Symlinked graph report')
        raw = report.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected or json.loads(raw).get('status') != 'PASS':
            raise ValueError('Changed or failed removal graph audit: '+name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def persist_graph(root):
    graph_receipt(root, archived=False)
    directory = root/'brave-work/.sandium/product-graph'
    if directory.is_symlink():raise ValueError('Symlinked graph evidence directory')
    directory.mkdir(exist_ok=True)
    for name in ('removal-graph-receipt.json',)+GRAPH_REPORTS:
        destination = directory/name
        if destination.is_symlink():raise ValueError('Symlinked archived graph evidence')
        temporary = destination.with_suffix('.tmp')
        if temporary.exists() or temporary.is_symlink():raise ValueError('Existing graph evidence staging file')
        with temporary.open('xb') as stream:
            stream.write((root/'brave-apk'/name).read_bytes());stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,destination)
    graph_receipt(root)  # Validate the copied receipt against copied report bytes.


def prepare(root):
    root = Path(root).resolve()
    admit(root)  # Compatibility must be reviewed before the first source write.
    proof = proof_path(root)
    if proof.exists() or proof.is_symlink():
        if proof.is_symlink():raise ValueError('Symlinked product proof')
        proof.unlink()  # Never retain an earlier ready claim across partial prep.
    src,core,out = root/'brave-work/src',root/'brave-work/src/brave',root/'brave-work/src/out/android_Release_arm64'
    python(root,'.circleci/scripts/apply-sandium-native-navigation.py',src,'--mode','off')
    python(root,'.circleci/scripts/apply-sandium-navigation-diagnostics.py',src,'--reset-native-probes')
    python(root,'.circleci/scripts/sandium-removal-recipe.py','--core',core,'--src',src,'--out',out,'--phase','reset')
    retire_reader(root)
    python(root,'.circleci/scripts/apply-sandium-full-overlays.py','--core',core,'--src',src)
    python(root,'.circleci/scripts/apply-sandium-fast-morphe.py',src)
    python(root,'.circleci/scripts/apply-sandium-filter-subscriptions.py','--core',core)
    for hook in ORDER:run(root,['bash',str(root/hook)])
    for phase in ('prepare','gn','verify'):
        python(root,'.circleci/upgrades/toolchain.py',phase,'--root',root)
    python(root,'.circleci/scripts/precheck-graph.py','--audits-only')
    python(root,'.circleci/scripts/removal-evidence.py','capture','--root',root)
    persist_graph(root)
    value = dict(schema=1,phase='build-ready',scope=os.environ['FULL_U_SCOPE'],
                 source=source_module().verify(root/'brave-work'),
                 graph=graph_hashes(root),removal_graph=graph_receipt(root))
    temporary = proof.with_suffix('.tmp')
    if temporary.exists() or temporary.is_symlink():raise ValueError('Existing product proof staging file')
    with temporary.open('x') as stream:
        json.dump(value,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,proof)
    return value


def verify(root):
    root = Path(root).resolve()
    admit(root)
    proof = proof_path(root)
    if proof.is_symlink():raise ValueError('Symlinked product proof')
    value = json.loads(proof.read_text())
    expected = dict(schema=1,phase='build-ready',scope=os.environ['FULL_U_SCOPE'],
                    source=source_module().verify(root/'brave-work'),
                    graph=graph_hashes(root),removal_graph=graph_receipt(root))
    if value != expected:raise ValueError('Stale product readiness proof')
    # Explicit host-prepare belongs to the caller. Never install, sync, reset,
    # repair sources or run GN generation while verifying an archived product.
    python(root,'.circleci/upgrades/toolchain.py','verify','--root',root)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan','prepare','verify','verify-base'))
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(globals()[args.command.replace('-', '_')](args.root), sort_keys=True))
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc))
