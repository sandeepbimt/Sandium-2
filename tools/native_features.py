"""Explicit native feature recipe. Caller retains source identity/foreign-change gates.

No manifest (or {}) means the unmodified baseline. Planning accepts only exact
upstream preimages or this recipe's postimages; verification requires all outputs.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'sandium/features/manifest.json'
FEATURES = ('menu', 'toolbar')
_IMPORT_LOCK = threading.RLock()


def load_manifest(root=ROOT):
    path = Path(root) / MANIFEST
    if not path.exists():
        return ()
    if path.is_symlink():
        raise ValueError('Feature manifest must not be a symlink')
    value = json.loads(path.read_text())
    if value == {}:
        return ()
    if (not isinstance(value, dict) or not {'schema', 'features'} <= set(value)
            or set(value) - {'schema', 'features', 'baseline', 'note'}
            or any(not isinstance(value[k], str) for k in ('baseline', 'note') if k in value)
            or type(value['schema']) is not int or value['schema'] != 1
            or not isinstance(value['features'], list)
            or any(not isinstance(x, str) or x not in FEATURES for x in value['features'])
            or len(set(value['features'])) != len(value['features'])):
        raise ValueError('Invalid explicit native feature manifest')
    return tuple(x for x in FEATURES if x in value['features'])


def recipe_inputs(root=ROOT):
    """Sorted repo-relative identity inputs, including the opt-in and this verifier."""
    root = Path(root)
    enabled = load_manifest(root)
    paths = {'tools/native_features.py'}
    if (root / MANIFEST).exists():
        paths.add(MANIFEST)
    for feature in enabled:
        directories = [root / 'experiments' / ('native-' + feature)]
        if feature == 'menu':
            directories.append(root / 'sandium/menu')
        for directory in directories:
            if not directory.is_dir():
                raise ValueError('Missing active feature directory: ' + str(directory))
            for path in directory.rglob('*'):
                if '__pycache__' in path.parts or path.suffix == '.pyc':
                    continue
                if path.is_symlink():
                    raise ValueError('Symlink in active feature recipe: ' + str(path))
                if path.is_file():
                    paths.add(path.relative_to(root).as_posix())
    return tuple(sorted(paths))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def _menu_modules(root):
    # grid_adapter has historical bare sibling imports. Temporarily bind only
    # these names, restore even on exceptions, and never import a foreign adapter.
    names = ('adapter', 'grid_input_adapter')
    with _IMPORT_LOCK:
        previous = {name: sys.modules.get(name) for name in names}
        present = {name for name in names if name in sys.modules}
        try:
            directory = root / 'experiments/native-menu'
            adapter = _load('_raws_menu_adapter', directory / 'adapter.py')
            sys.modules['adapter'] = adapter
            sys.modules['grid_input_adapter'] = _load(
                '_raws_menu_input_adapter', directory / 'grid_input_adapter.py')
            yield adapter, _load('_raws_menu_grid_adapter', directory / 'grid_adapter.py')
        finally:
            for name in names:
                if name in present:
                    sys.modules[name] = previous[name]
                else:
                    sys.modules.pop(name, None)


@dataclass(frozen=True)
class FeaturePlan:
    tracked_paths: frozenset
    generated_paths: frozenset
    expected: dict  # repo-relative source path -> exact UTF-8 postimage text
    hashes: dict  # same source paths -> SHA256 of expected bytes


def _safe_target(source, relative):
    target = source / relative
    for path in (target, *target.parents):
        if path == source:
            break
        if path.is_symlink():
            raise ValueError('Symlink in feature output path: ' + relative)
    return target


def plan(source, root=ROOT):
    source, root = Path(source), Path(root)
    enabled = load_manifest(root)
    # Validate input enumeration before importing any active recipe.
    recipe_inputs(root)
    expected, originals = {}, {}
    for feature in enabled:
        if feature == 'menu':
            with _menu_modules(root) as (adapter, grid):
                tracked = (adapter.HANDLER, adapter.BUILD, grid.APP, grid.DRAG)
                for relative in tracked:
                    _safe_target(source, relative)
                outputs = grid.plan(source)
                fixtures = root / 'experiments/native-menu/fixtures'
        else:
            adapter = _load('_raws_toolbar_adapter', root / 'experiments/native-toolbar/adapter.py')
            tracked = (adapter.PHONE, adapter.PROGRESS)
            for relative in tracked:
                _safe_target(source, relative)
            outputs = adapter.plan(source)
            fixtures = root / 'experiments/native-toolbar/fixtures'
        for relative in tracked:
            originals[relative] = (fixtures / Path(relative).name).read_bytes()
        for target, content in outputs.items():
            relative = target.relative_to(source).as_posix()
            if relative in expected:
                raise ValueError('Overlapping native feature output: ' + relative)
            expected[relative] = content
    if 'menu' in enabled:
        # Only feature-owned names, never a broad Chromium/DEPS untracked gate.
        java = source / 'chrome/browser/ui/android/appmenu/internal/java/src/org/chromium/chrome/browser/ui/appmenu'
        resources = source / 'chrome/browser/ui/android/appmenu/internal/java/res'
        owned = list(java.glob('RawS*.java')) + list(resources.rglob('raws_menu*.xml'))
        for path in owned:
            relative = path.relative_to(source).as_posix()
            if relative not in expected:
                raise ValueError('Unexpected feature-owned source: ' + relative)
    for relative, content in expected.items():
        target = _safe_target(source, relative)
        if target.exists():
            permitted = [content.encode()]
            if relative in originals:
                permitted.append(originals[relative])
            if target.read_bytes() not in permitted:
                raise ValueError('Unreviewed feature output bytes: ' + relative)
        elif relative in originals:
            raise ValueError('Missing upstream feature source: ' + relative)
    return FeaturePlan(frozenset(originals), frozenset(set(expected) - set(originals)),
                       expected, {p: hashlib.sha256(t.encode()).hexdigest()
                                  for p, t in expected.items()})


def verify_applied(source, root=ROOT):
    result = plan(source, root)
    for relative, content in result.expected.items():
        path = Path(source) / relative
        if not path.is_file() or path.read_bytes() != content.encode():
            raise ValueError('Native feature not completely applied: ' + relative)
    return result


def apply(source, root=ROOT):
    """Preflight entire combined recipe before writes; resumable exact replay only."""
    result = plan(source, root)
    for relative, content in result.expected.items():
        path = Path(source) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode())
    return verify_applied(source, root)
