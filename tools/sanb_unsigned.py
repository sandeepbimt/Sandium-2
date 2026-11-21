"""SanB's narrow unsigned target switch, against the exact public M158 GN files."""
import hashlib

INTERNAL = "build/config/android/internal_rules.gni"
RULES = "build/config/android/rules.gni"
PINS = {
    INTERNAL: "3220f78bad56a61ec65c1becf48fd4dc67a202c4",
    RULES: "a3829f7f3af10720ff7459ba4ebb43605d679ed7",
    "build/android/gyp/apkbuilder.py": "caf962fd5e45b3e6d7e4cbd1207218ee77255015",
    "build/android/gyp/util/zipbuilder.py": "21f016f71c323ef7e8956ea046772495546d341a",
}


def git_blob(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def once(old, needle, new):
    if old.count(needle) != 1:
        raise ValueError("SanB unsigned packager: pinned GN context changed")
    return old.replace(needle, new)


def postimages(src):
    before = {}
    for path, pin in PINS.items():
        p = src / path
        if p.is_symlink() or not p.is_file() or p.resolve() != src.resolve() / path:
            raise ValueError("SanB unsigned packager: missing regular pinned file " + path)
        b = p.read_bytes()
        if git_blob(b) != pin:
            raise ValueError("SanB unsigned packager: Bare port overlaps pinned source " + path)
        before[path] = b
    internal = once(before[INTERNAL], b"    if (!_is_robolectric_apk) {\n      _keystore_path",
                    b"    if (!_is_robolectric_apk &&\n"
                    b"        (!defined(invoker.sanb_unsigned) || !invoker.sanb_unsigned)) {\n"
                    b"      _keystore_path")
    rules = once(before[RULES], b'  import("//build/config/gclient_args.gni")\n}\n',
                 b'  import("//build/config/gclient_args.gni")\n}\n\n'
                 b"declare_args() {\n  sanb_unsigned_apk = false\n}\n")
    rules = once(rules, b'      package_apk("$_create_apk_target") {\n',
                 b'      package_apk("$_create_apk_target") {\n'
                 b'        sanb_unsigned = sanb_unsigned_apk &&\n'
                 b'                        _template_name == "chrome_public_apk" &&\n'
                 b'                        get_label_info("//chrome/android:chrome_public_apk",\n'
                 b'                                       "dir") == get_label_info(":$_create_apk_target", "dir")\n')
    return {src / INTERNAL: (before[INTERNAL], internal), src / RULES: (before[RULES], rules)}


def apply(src):
    """Use only in this disposable SanB worker; never restore/reuse those output files."""
    values = postimages(src)
    for path, (old, data) in values.items():
        if path.read_bytes() != old:
            raise ValueError("SanB unsigned packager: source drift during apply")
        path.write_bytes(data)
    verify(values)
    return values


def verify(values):
    for path, (_, data) in values.items():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != data:
            raise ValueError("SanB unsigned packager: exact composed bytes drifted")
