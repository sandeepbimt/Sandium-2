"""Token-free, exact-file admission for a reviewed RawS restore-only source overlay.

The exact combined UI and engine manifest is pinned here. A manifest cannot run code, choose an engine, or alter a cache key.
"""

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess

from ci_timing import prep_phase
from raw import verify as verify_baseline
from restore_only_menu_ui import (
    MENU_PARITY_TRACKED, MENU_PARITY_JAVA, MENU_PARITY_RESOURCES, MENU_RESOURCE_DIR,
)
from source_compat import SISO_MAIN, patched_siso

RECIPE = 'raws-adblock/production-restore-recipe.json'
POSTIMAGES = 'raws-adblock/production-postimages'
# Set only after independent production source review and exact bytes are final.
APPROVED_MANIFEST_SHA256 = '7081e486a25eb33a74cac59bec9e94b16030f9b7c091b1e5faab2fc95c977aeb'
# A combined candidate, when pinned, replaces the engine-only admission.
# It must not fall back to the older digest if the UI manifest is missing.
APPROVED_UI_MANIFEST_SHA256 = 'f4ce56b0d58bc3ff93b39a35d79c6ecb1d104fd5d1139ec1cc2975bb59c28c83'
APPROVED_UI_TRACKED = frozenset((
    'chrome/android/chrome_java_resources.gni',
    'chrome/android/chrome_java_sources.gni',
    'chrome/android/java/res/xml/main_preferences.xml',
    'chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java',
    'chrome/android/java/src/org/chromium/chrome/browser/settings/MainSettings.java',
    'chrome/android/java/src/org/chromium/chrome/browser/signin/SigninFirstRunFragment.java',
    'chrome/android/java/src/org/chromium/chrome/browser/tabbed_mode/TabbedAppMenuPropertiesDelegate.java',
    'chrome/browser/ui/android/appmenu/internal/BUILD.gn',
    'chrome/browser/ui/android/appmenu/internal/java/src/org/chromium/chrome/browser/ui/appmenu/AppMenuHandlerImpl.java',
    'chrome/browser/ui/android/appmenu/java/src/org/chromium/chrome/browser/ui/appmenu/AppMenuHandler.java',
    'chrome/browser/ui/android/appmenu/java/src/org/chromium/chrome/browser/ui/appmenu/AppMenuPropertiesDelegate.java',
    'chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/ToolbarPhone.java',
)) | MENU_PARITY_TRACKED
APPROVED_GN_COMPAT_TRACKED = frozenset((
    'third_party/rust/unicode_ident/v1/BUILD.gn',
    'third_party/rust/aho_corasick/v1/BUILD.gn',
    'third_party/rust/bitflags/v2/BUILD.gn',
    'third_party/rust/cfg_if/v1/BUILD.gn',
    'third_party/rust/itoa/v1/BUILD.gn',
    'third_party/rust/memchr/v2/BUILD.gn',
    'third_party/rust/regex_automata/v0_4/BUILD.gn',
    'third_party/rust/regex_syntax/v0_8/BUILD.gn',
    'third_party/rust/serde/v1/BUILD.gn',
    'third_party/rust/serde_core/v1/BUILD.gn',
))
UI_GENERATED = frozenset((
    'chrome/android/java/res/anim/raws_settings_fade_in.xml',
    'chrome/android/java/res/anim/raws_settings_fade_out.xml',
    'chrome/android/java/res/animator/raws_settings_fade_in.xml',
    'chrome/android/java/res/animator/raws_settings_fade_out.xml',
    'chrome/android/java/res/values/raws_video_strings.xml',
    'components/browser_ui/styles/android/java/res/color/raws_sandium_switch_thumb.xml',
    'components/browser_ui/styles/android/java/res/color/raws_sandium_switch_track.xml',
    'chrome/android/java/res/drawable-nodpi/raws_home_wallpaper.webp',
    'chrome/browser/ui/android/toolbar/java/res/values/raws_address_controls.xml',
    'chrome/browser/ui/android/toolbar/java/res/drawable/raws_page_toolbar_forward.xml',
    'chrome/browser/ui/android/toolbar/java/res/drawable/raws_page_toolbar_menu.xml',
    'chrome/android/java/res/drawable-nodpi/raws_frozen_shields_mark.webp',
    'chrome/android/java/res/drawable/raws_frozen_shields_card.xml',
    'chrome/android/java/res/drawable/raws_frozen_shields_dns_picker.xml',
    'chrome/android/java/res/drawable/raws_frozen_shields_rim.xml',
    'chrome/android/java/src/org/chromium/chrome/browser/settings/SandiumBalancedTracer.java',
    'chrome/android/java/res/drawable/raws_global_shield_icon.xml',
    'chrome/android/java/res/layout/raws_global_shield_sheet.xml',
    'chrome/android/java/res/values-night/raws_main_settings_palette.xml',
    'chrome/android/java/res/values-night/raws_welcome_palette.xml',
    'chrome/android/java/res/values/raws_global_shield_strings.xml',
    'chrome/android/java/res/values/raws_main_settings_palette.xml',
    'chrome/android/java/res/values/raws_main_settings_strings.xml',
    'chrome/android/java/res/values/raws_welcome_palette.xml',
    'chrome/android/java/res/xml/raws_protection_preferences.xml',
    'chrome/android/java/src/org/chromium/chrome/browser/settings/RawsGlobalShieldSheet.java',
    'chrome/android/java/src/org/chromium/chrome/browser/settings/RawsProtectionCopy.java',
    'chrome/android/java/src/org/chromium/chrome/browser/settings/RawsProtectionSettings.java',
    'chrome/browser/ui/android/appmenu/internal/java/res/values-hi/raws_menu.xml',
    'chrome/browser/ui/android/appmenu/internal/java/res/values/raws_menu.xml',
    'chrome/browser/ui/android/appmenu/internal/java/src/org/chromium/chrome/browser/ui/appmenu/RawSMenuModel.java',
    'chrome/browser/ui/android/appmenu/internal/java/src/org/chromium/chrome/browser/ui/appmenu/RawSMenuStore.java',
    'chrome/browser/ui/android/appmenu/internal/java/src/org/chromium/chrome/browser/ui/appmenu/RawSNativeMenu.java',
)) | MENU_PARITY_JAVA | MENU_PARITY_RESOURCES
UI_RESOURCE_FILES = frozenset(name for name in UI_GENERATED if '/res/' in name)
UI_RESOURCE_DIRS = frozenset(str(PurePosixPath(name).parent) for name in UI_RESOURCE_FILES)
TRACKED = frozenset(('chrome/browser/BUILD.gn',
                     'chrome/browser/browser_resources.grd',
                     'chrome/browser/chrome_browser_main_android.cc',
                     'chrome/browser/chrome_content_browser_client.cc'))
COMPONENT = 'components/sandium_adblock'
LISTS = 'chrome/browser/resources/raws'
LIST_FILES = frozenset((LISTS + '/easylist.txt', LISTS + '/NOTICE-EASYLIST.md'))
OWNED = ('brave', COMPONENT, LISTS)
BRAVE_STAGE = '.raws-staged-engine'
BRAVE_INVENTORY = Path(__file__).with_name('restore_only_brave_inventory.json')
BRAVE_INVENTORY_SHA256 = 'e550c7e7c58ebc6a09ff282699b22226beee2aaec108f88122d5e55c761c21c9'
HEX = re.compile(r'[0-9a-f]{64}')
FILE = re.compile(r'[A-Za-z0-9_./+-]+')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe(root, relative):
    path = PurePosixPath(relative)
    if (not FILE.fullmatch(relative) or path.is_absolute()
            or '..' in path.parts or '.git' in path.parts or path.as_posix() != relative):
        raise ValueError('Unsafe feature path: ' + relative)
    candidate = root / path
    for part in (candidate, *candidate.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError('Feature path is a symlink: ' + relative)
    return candidate


def read_regular(path):
    if not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('Missing or non-regular feature input: ' + str(path))
    return path.read_bytes()


def brave_inventory():
    raw = read_regular(BRAVE_INVENTORY)
    if sha(raw) != BRAVE_INVENTORY_SHA256:
        raise ValueError('Frozen Brave dependency closure differs')
    return json.loads(raw)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def dirs_for(files, root):
    return {p.as_posix() for name in files for p in PurePosixPath(name).parents
            if p.as_posix().startswith(root + '/') or p.as_posix() == root}


def exact_tree(root, directory, files):
    # Compare the full owned subtree including directories, hidden files and
    # symlinks, not merely the set of paths the overlay intends to write.
    tree = safe(root, directory)
    actual_files, actual_dirs = set(), {directory}
    if not tree.is_dir():
        raise ValueError('Missing generated feature subtree: ' + directory)
    for path in tree.rglob('*'):
        relative = path.relative_to(root).as_posix()
        safe(root, relative)
        if path.is_dir():
            actual_dirs.add(relative)
        elif stat.S_ISREG(path.lstat().st_mode):
            actual_files.add(relative)
        else:
            raise ValueError('Non-regular generated feature file: ' + relative)
    if actual_files != files or actual_dirs != dirs_for(files, directory):
        raise ValueError('Generated feature inventory differs: ' + directory)


def approved_manifest_sha256():
    return (APPROVED_UI_MANIFEST_SHA256 if APPROVED_UI_MANIFEST_SHA256 is not None
            else APPROVED_MANIFEST_SHA256)


def ui_resource_prefixes(directory):
    return ('raws_', 'sandium_menu_') if directory.startswith(MENU_RESOURCE_DIR) else ('raws_',)


def exact_ui_resources(src, ui_files, *, installed=True):
    # These are shared Chromium directories, not overlay-owned subtrees. Derive
    # the reserved files from the full approved UI inventory, including the
    # exact port proof's extra_generated paths. Non-reserved native resources
    # remain outside this namespace check.
    expected = set()
    directories = set(UI_RESOURCE_DIRS)
    for relative in ui_files:
        if '/res/' not in relative:
            continue
        resource = PurePosixPath(relative)
        parent = resource.parent.as_posix()
        if resource.name.startswith(ui_resource_prefixes(parent)):
            directories.add(parent)
            if installed:
                expected.add(relative)

    found = set()
    for relative in sorted(directories):
        directory = safe(src, relative)
        if not directory.exists() and not expected:
            # The recipe may add a locale qualifier.
            continue
        if not directory.is_dir():
            raise ValueError('Missing pinned Settings resource directory: ' + relative)
        for prefix in ui_resource_prefixes(relative):
            for entry in directory.glob(prefix + '*'):
                name = entry.relative_to(src).as_posix()
                safe(src, name)
                if not stat.S_ISREG(entry.lstat().st_mode):
                    raise ValueError('Non-regular Settings generated resource: ' + name)
                found.add(name)
    if found != expected:
        missing = sorted(expected - found)
        unexpected = sorted(found - expected)
        raise ValueError('Generated Settings resource inventory differs: '
                         f'missing ({len(missing)}) {missing[:8]}; '
                         f'unexpected ({len(unexpected)}) {unexpected[:8]}')


def load(recipe_root, base_fingerprint, chromium_revision):
    """Return None for ordinary baseline; reject present but unreviewed manifests."""
    root = Path(recipe_root).resolve()
    path = safe(root, RECIPE)
    approved = approved_manifest_sha256()
    if not path.exists():
        if approved is not None:
            raise ValueError('Approved RawS production feature recipe is missing')
        return None
    raw = read_regular(path)
    identity = sha(raw)
    if identity != approved:
        raise ValueError('Unreviewed RawS production feature recipe')
    value = json.loads(raw)
    if (set(value) != {'schema', 'baseline_fingerprint', 'chromium_revision', 'files'}
            or type(value['schema']) is not int or value['schema'] != 1
            or value['baseline_fingerprint'] != base_fingerprint
            or value['chromium_revision'] != chromium_revision or not isinstance(value['files'], dict)):
        raise ValueError('Feature recipe identity differs from verified baseline')
    scope = brave_inventory()
    ui_enabled = APPROVED_UI_MANIFEST_SHA256 is not None
    tracked_paths = (TRACKED | APPROVED_UI_TRACKED | APPROVED_GN_COMPAT_TRACKED) if ui_enabled else TRACKED
    ui_files = UI_GENERATED if ui_enabled else frozenset()
    from restore_only_port1442 import proof as reviewed_port
    port = reviewed_port()
    if port is not None:
        if not ui_enabled or port["manifest_sha256"] != identity:
            raise ValueError("Reviewed #1442 port must extend existing RawS feature")
        tracked_paths |= frozenset(port["extra_tracked"])
        ui_files |= frozenset(port["extra_generated"])
    files = {}
    for relative, entry in value['files'].items():
        safe(root, relative)
        tracked = relative in tracked_paths
        brave = relative.startswith('brave/')
        if brave:
            allowed = relative in scope['standalone'] or any(
                relative.startswith(prefix + '/') for prefix in scope['roots'])
        else:
            allowed = (tracked or relative in LIST_FILES or relative in ui_files
                       or relative.startswith(COMPONENT + '/'))
        if not allowed:
            raise ValueError('Feature path outside reviewed scope: ' + relative)
        if (not isinstance(entry, dict) or
                set(entry) not in ({'before_sha256', 'after_sha256'},
                                   {'before_sha256', 'after_sha256', 'mode'})):
            raise ValueError('Invalid feature inventory record: ' + relative)
        before, after = entry['before_sha256'], entry['after_sha256']
        mode = entry.get('mode', '644')
        if mode not in (('644', '755') if brave else ('644',)):
            raise ValueError('Invalid feature file mode: ' + relative)
        if (tracked and (not isinstance(before, str) or not HEX.fullmatch(before))
                or not tracked and before is not None
                or not isinstance(after, str) or not HEX.fullmatch(after) or before == after):
            raise ValueError('Invalid feature preimage/postimage digest: ' + relative)
        files[relative] = (before, after, mode)
    if not (tracked_paths | LIST_FILES | ui_files) <= files.keys() or not any(
            name.startswith(COMPONENT + '/') for name in files):
        raise ValueError('Incomplete production feature inventory')
    brave = {name: mode for name, (_, _, mode) in files.items() if name.startswith('brave/')}
    if (len(brave) != scope['leaf_count']
            or sha(canonical(brave)) != scope['leaf_path_mode_sha256']):
        raise ValueError('Brave source inventory differs from exact frozen stage.py closure')
    if any(name in files for directory in OWNED for name in dirs_for(files, directory)):
        raise ValueError('File and directory overlap in production feature inventory')
    return Overlay(identity, files, root, tracked_paths, ui_files)


def git(src, *args, input=None):
    return subprocess.check_output(['git', '--no-replace-objects', '-C', str(src), *args],
                                   input=input, timeout=600)


class Overlay:
    def __init__(self, identity, files, recipe_root, tracked_paths, ui_files):
        self.identity = identity
        self.files = files
        self.recipe_root = recipe_root
        self.tracked_paths = tracked_paths
        self.ui_files = ui_files
        self.has_ui = bool(ui_files)
        # Only immutable, manifest-verified Git preimages are reused. No live
        # path, file content/mode, namespace or baseline check is cached.
        self._pinned = None

    def generated(self, directory):
        return {name for name in self.files if name.startswith(directory + '/')}

    def postimages(self):
        stage = safe(self.recipe_root, BRAVE_STAGE)
        exact_tree(stage, 'brave', self.generated('brave'))
        result = {}
        for relative, (_, after, mode) in self.files.items():
            brave = relative.startswith('brave/')
            location = (safe(stage, relative) if brave else
                        safe(self.recipe_root, POSTIMAGES + '/' + after))
            data = read_regular(location)
            if sha(data) != after:
                raise ValueError('Feature payload hash mismatch: ' + relative)
            if brave and stat.S_IMODE(location.stat().st_mode) != int(mode, 8):
                raise ValueError('Brave staged input file mode mismatch: ' + relative)
            result[relative] = data
        return result

    def _pinned_preimages(self, src, revision):
        expected = {name: before for name, (before, _, _) in self.files.items()
                    if before is not None}
        key = (src, revision, tuple(expected.items()))
        if self._pinned is not None and self._pinned[0] == key:
            return self._pinned[1]
        if not expected:
            return {}
        paths = {name.encode(): name for name in expected}
        objects = {}
        # Explicit literal paths and commit, not the mutable working tree or
        # an implicit HEAD which could move between the revision and blob reads.
        records = git(src, '--literal-pathspecs', 'ls-tree', '-z', revision, '--', *expected)
        for record in records.split(b'\0')[:-1]:
            entry, sep, raw_path = record.partition(b'\t')
            name = paths.get(raw_path)
            info = re.fullmatch(rb'100644 blob ([0-9a-f]{40}|[0-9a-f]{64})', entry)
            if not sep or name is None or name in objects or info is None:
                raise ValueError('Feature preimage Git mode mismatch: ' + str(name or raw_path))
            objects[name] = info.group(1)
        if not records.endswith(b'\0') or objects.keys() != expected.keys():
            raise ValueError('Feature preimage Git mode mismatch: ' +
                             ', '.join(sorted(expected.keys() - objects.keys())))
        # One bounded subprocess, no per-file Git startup. Headers bind each
        # blob to its tree ID; SHA-256 binds its bytes to the reviewed recipe.
        output = io.BytesIO(git(src, 'cat-file', '--batch',
                                input=b''.join(oid + b'\n' for oid in objects.values())))
        originals = {}
        for name, oid in objects.items():
            header = output.readline()
            info = re.fullmatch(oid + rb' blob ([0-9]+)\n', header)
            if info is None:
                raise ValueError('Unexpected Git preimage response: ' + name)
            size = int(info.group(1))
            data = output.read(size)
            if len(data) != size or output.read(1) != b'\n':
                raise ValueError('Truncated Git preimage: ' + name)
            actual = sha(data)
            if actual != expected[name]:
                raise ValueError(f'Feature preimage digest mismatch: {name}: '
                                 f'pinned={actual} expected={expected[name]}')
            originals[name] = data
        if output.read(1):
            raise ValueError('Unexpected trailing Git preimage response')
        self._pinned = (key, originals)
        return originals

    def preflight(self, source, upstream):
        """Validate every live destination without writes."""
        src = Path(source).resolve()
        revision = upstream['chromium']['revision']
        if git(src, 'rev-parse', 'HEAD').decode().strip() != revision:
            raise ValueError('Wrong Chromium revision')
        originals = self._pinned_preimages(src, revision)
        for directory in OWNED:
            if safe(src, directory).exists():
                if directory == 'brave':
                    raise ValueError('Brave directory present in clean baseline')
                raise ValueError('Generated feature directory must not preexist: ' + directory)
        if self.ui_files:
            exact_ui_resources(src, self.ui_files, installed=False)
        targets = {}
        for relative, (before, _, mode) in self.files.items():
            path = safe(src, relative)
            if before is not None:
                original = originals[relative]
                restored = read_regular(path)
                if restored != original:
                    raise ValueError(f'Feature preimage bytes mismatch: {relative}: '
                                     f'restored={sha(restored)} expected={before}')
                # The same non-executable Git file can be group-writable on
                # shared checkout/restore workers. No other mode is admitted.
                actual = stat.S_IMODE(path.lstat().st_mode)
                if actual not in (0o644, 0o664):
                    raise ValueError(f'Feature preimage disk mode mismatch: {relative}: '
                                     f'restored={actual:04o} allowed=0644,0664')
            elif path.exists():
                raise ValueError('Generated feature path must not preexist: ' + relative)
            targets[relative] = (path, mode)
        return targets

    def apply(self, source, upstream):
        """Verify exact preimages and payload again before writing any bytes."""
        with prep_phase('feature-baseline-recheck'):
            verify_baseline(Path(source).resolve(), upstream)
        with prep_phase('feature-payload-verification'):
            postimages = self.postimages()
        with prep_phase('feature-live-destination-recheck'):
            targets = self.preflight(source, upstream)
        with prep_phase('feature-materialization'):
            for relative, (path, mode) in targets.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(postimages[relative])
                path.chmod(int(mode, 8))
        with prep_phase('feature-installed-verification'):
            self.verify(source, upstream)

    def verify(self, source, upstream):
        """Check engine postimages without relaxing any original source guard."""
        src = Path(source).resolve()
        if git(src, 'rev-parse', 'HEAD').decode().strip() != upstream['chromium']['revision']:
            raise ValueError('Wrong Chromium revision')
        changed = set(git(src, 'diff', 'HEAD', '--name-only', '-z').decode().split('\0')) - {''}
        if not self.tracked_paths <= changed or changed - self.tracked_paths - {SISO_MAIN}:
            raise ValueError('Unapproved tracked Chromium changes present')
        if git(src, 'diff', 'HEAD', '--diff-filter=T', '--name-only', '-z'):
            raise ValueError('Unreviewed tracked file type changes')
        if SISO_MAIN in changed:
            original = git(src, 'show', 'HEAD:' + SISO_MAIN).decode()
            if read_regular(safe(src, SISO_MAIN)) != patched_siso(original).encode():
                raise ValueError('Unexpected Siso compatibility source')
        version = dict(line.split('=', 1) for line in
                       (src / 'chrome/VERSION').read_text().splitlines())
        if '.'.join(version[k] for k in ('MAJOR', 'MINOR', 'BUILD', 'PATCH')) != upstream['chromium']['version']:
            raise ValueError('Version does not match lock')
        for directory in OWNED:
            exact_tree(src, directory, self.generated(directory))
        if self.ui_files:
            exact_ui_resources(src, self.ui_files)
        for relative, (_, after, mode) in self.files.items():
            path = safe(src, relative)
            if sha(read_regular(path)) != after or stat.S_IMODE(path.stat().st_mode) != int(mode, 8):
                raise ValueError('Feature postimage changed: ' + relative)
