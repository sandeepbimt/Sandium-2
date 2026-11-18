"""Dormant Android GN/source registration. Never imported by the active planner."""
from pathlib import Path

COMPONENTS = (
    "content/public/browser/android/native_page_handoff_snapshot.h",
    "content/public/browser/android/native_page_handoff_observation_owner.h",
    "content/browser/android/native_page_handoff_snapshot.cc",
    "content/browser/android/native_page_handoff_observation_owner.cc",
)
ADDITIONS = {
    "content/browser/BUILD.gn": (
        '      "android/navigation_handle_proxy.cc",\n',
        '      "android/native_page_handoff_observation_owner.cc",\n'
        '      "android/native_page_handoff_snapshot.cc",\n'),
    "content/public/browser/BUILD.gn": (
        '      "android/motion_event_action.h",\n',
        '      "android/native_page_handoff_observation_owner.h",\n'
        '      "android/native_page_handoff_snapshot.h",\n'),
}

def transform(path, text):
    anchor, addition = ADDITIONS[path]
    if text.count(anchor) != 1:
        raise ValueError("Pinned GN anchor drift: " + path)
    entries = addition.splitlines(keepends=True)
    counts = [text.count(entry) for entry in entries]
    if any(counts):
        if counts != [1] * len(entries) or addition not in text:
            raise ValueError("Partial/duplicate handoff registration: " + path)
        expected = addition + anchor if path == "content/browser/BUILD.gn" else anchor + addition
        if expected not in text:
            raise ValueError("Moved handoff registration: " + path)
        return text
    return text.replace(anchor, addition + anchor if path == "content/browser/BUILD.gn" else anchor + addition, 1)

def plan(root):
    root = Path(root)
    result = {}
    for path in ADDITIONS:
        result[root / path] = transform(path, (root / path).read_text())
    base = Path(__file__).parent / "components"
    for path in COMPONENTS:
        source = (base / path).read_text()
        target = root / path
        if target.exists() and target.read_text() != source:
            raise ValueError("Refusing to replace different existing component: " + path)
        result[target] = source
    return result
