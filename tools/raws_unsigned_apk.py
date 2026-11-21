"""Exact M158 Chromium packaging opt-in for the private RawS signer."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import zipfile

ARG = 'raws_unsigned_test_apk'
APK_ACTION = '//chrome/android:chrome_public_apk__create'
JAVA_BODY_JAR = 'obj/chrome/android/chrome_java.javac.jar'
PINS = {
    'build/config/android/internal_rules.gni': '3220f78bad56a61ec65c1becf48fd4dc67a202c4',
    'build/config/android/rules.gni': 'a3829f7f3af10720ff7459ba4ebb43605d679ed7',
    'build/android/gyp/apkbuilder.py': 'caf962fd5e45b3e6d7e4cbd1207218ee77255015',
    'build/android/gyp/util/zipbuilder.py': '21f016f71c323ef7e8956ea046772495546d341a',
}
SIGN_FIELDS = ('apk_unsigned_verified', 'apk_zipalign_16k_verified',
               'apk_unsigned_packaging_graph_verified')
_SIGN_MAGIC = b'APK Sig Block 42'
_V1_SIG = re.compile(r'META-INF/(?:[^/]+\.(?:SF|RSA|DSA|EC)|SIG-[^/]+)', re.I)


def mode():
    value = os.environ.get('RAWS_UNSIGNED_TEST_APK', 'false')
    if value not in ('true', 'false'):
        raise ValueError('Malformed RawS unsigned packaging selector')
    return value == 'true'


def append_arg(args):
    if re.search(r'^\s*' + ARG + r'\s*=', args, re.M):
        raise ValueError('RawS unsigned GN switch already assigned')
    return args.rstrip('\n') + '\n' + ARG + ' = true\n'


def git_blob(value):
    return hashlib.sha1(b'blob %d\x00' % len(value) + value).hexdigest()


def replace_once(data, old, new):
    if data.count(old) != 1:
        raise ValueError('Pinned RawS packaging context does not match')
    return data.replace(old, new)


def patch_files(src):
    """Return exact input/postimage tuples; fail before writing on any drift."""
    values = {}
    for name, pin in PINS.items():
        path = src / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing pinned RawS ZIP packaging source: ' + name)
        data = path.read_bytes()
        if git_blob(data) != pin:
            raise ValueError('Unexpected pinned RawS ZIP packaging source: ' + name)
        values[name] = data

    internal = 'build/config/android/internal_rules.gni'
    rules = 'build/config/android/rules.gni'
    orig = values[internal]
    new = replace_once(orig, b'  # Creates a signed and aligned .apk.',
                       b'  # Creates an aligned .apk (signed unless explicitly unsigned).')
    new = replace_once(new, b'  #   keystore_password: Keystore password.\n  template("package_apk")',
                       b'  #   keystore_password: Keystore password.\n'
                       b'  #   raws_unsigned: Leave this APK unsigned for the isolated RawS signer.\n'
                       b'  template("package_apk")')
    new = replace_once(new, b'    if (!_is_robolectric_apk) {\n      _keystore_path',
                       b'    if (!_is_robolectric_apk &&\n'
                       b'        (!defined(invoker.raws_unsigned) || !invoker.raws_unsigned)) {\n'
                       b'      _keystore_path')
    top = replace_once(values[rules], b'  import("//build/config/gclient_args.gni")\n}\n',
                       b'  import("//build/config/gclient_args.gni")\n}\n\n'
                       b'declare_args() {\n  raws_unsigned_test_apk = false\n}\n')
    top = replace_once(top, b'      package_apk("$_create_apk_target") {\n',
                       b'      package_apk("$_create_apk_target") {\n'
                       b'        raws_unsigned = raws_unsigned_test_apk &&\n'
                       b'                        _template_name == "chrome_public_apk" &&\n'
                       b'                        get_label_info("//chrome/android:chrome_public_apk",\n'
                       b'                                       "dir") == get_label_info(":$_create_apk_target", "dir")\n')
    return {src / internal: (orig, new), src / rules: (values[rules], top)}


class PackagingOverlay:
    """Temporary strictly pinned GN edits; keep the checkpoint source intact."""
    def __init__(self, src):
        self.files = patch_files(src)
        self.applied = []

    def apply(self):
        for path, (baseline, postimage) in self.files.items():
            if path.is_symlink() or path.read_bytes() != baseline:
                raise ValueError('RawS packaging source drifted before overlay')
            self.applied.append(path)
            path.write_bytes(postimage)

    def verify(self):
        for path, (_, postimage) in self.files.items():
            if path.is_symlink() or path.read_bytes() != postimage:
                raise ValueError('RawS packaging source drifted during build')

    def restore(self):
        while self.applied:
            path = self.applied[-1]
            baseline = self.files[path][0]
            if path.is_symlink():
                raise ValueError('RawS packaging source became a symlink')
            path.write_bytes(baseline)
            self.applied.pop()


def verify_graph(src, gn, out, env):
    def query(fields):
        return subprocess.check_output(
            [str(gn), 'desc', str(out), APK_ACTION, fields],
            cwd=src, env=env, text=True, timeout=45,
        ).splitlines()
    args, ins, outputs = (query(f) for f in ('args', 'inputs', 'outputs'))
    if (not any('--output-apk=' in v and v.rstrip().endswith('/ChromePublic.apk') for v in args)
            or not any(v.strip().endswith('/ChromePublic.apk') for v in outputs)
            or any('ChromePublic.apk.idsig' in v for v in outputs)
            or any(re.search(r'--key-(?:path|name|passwd)(?:\s|$|=)', v) for v in args)
            or any(re.search(r'\.(?:jks|keystore|p12|pfx)\s*$', v, re.I) for v in ins)
            or not any('signflinger' in v for v in ins)):
        raise ValueError('RawS GN package action did not omit APK signing')
    return True


def verify_zip(apk, *, unsigned):
    if apk.is_symlink() or not apk.is_file():
        raise ValueError('Not a regular RawS APK')
    if unsigned and Path(str(apk) + '.idsig').exists():
        raise ValueError('Unexpected RawS APK v4 signature sidecar')
    with zipfile.ZipFile(apk) as z:
        names = z.namelist()
        if (len(set(names)) != len(names) or 'AndroidManifest.xml' not in names
                or z.testzip() is not None):
            raise ValueError('RawS APK ZIP structure or checksum is invalid')
        abis = {name.split('/')[1] for name in names
                if name.startswith('lib/') and name.count('/') >= 2 and name.endswith('.so')}
        if abis != {'arm64-v8a'}:
            raise ValueError('RawS APK must contain only arm64-v8a native libraries')
        if unsigned:
            if any(_V1_SIG.fullmatch(name) for name in names):
                raise ValueError('RawS private candidate contains a v1 signature')
            with apk.open('rb') as stream:
                # Android v2/v3 signing blocks end immediately before the central directory.
                if z.start_dir >= len(_SIGN_MAGIC):
                    stream.seek(z.start_dir - len(_SIGN_MAGIC))
                    if stream.read(len(_SIGN_MAGIC)) == _SIGN_MAGIC:
                        raise ValueError('RawS private candidate contains an APK signing block')
    return sorted(abis)


def verify_aligned(apk, zipalign, env):
    try:
        subprocess.run([str(zipalign), '-c', '-P', '16', '4', str(apk)], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=120)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        raise ValueError('RawS APK failed SDK 16 KiB ZIP alignment verification') from None
