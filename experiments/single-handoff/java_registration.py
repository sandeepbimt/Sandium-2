"""Dormant Java target registration; respects lower tab vs upper browser layering."""
from pathlib import Path
PACKAGE = "org/chromium/chrome/browser/tab/"
COMPONENTS = {
    "chrome/browser/tab/java/src/" + PACKAGE + "NativePageHandoffOffer.java": PACKAGE + "NativePageHandoffOffer.java",
    "chrome/browser/tab/java/src/" + PACKAGE + "NativePageHandoffSource.java": PACKAGE + "NativePageHandoffSource.java",
}
ADDITIONS = {
    "chrome/browser/tab/BUILD.gn": (
        '    "java/src/org/chromium/chrome/browser/tab/SadTab.java",\n',
        '    "java/src/org/chromium/chrome/browser/tab/NativePageHandoffOffer.java",\n'
        '    "java/src/org/chromium/chrome/browser/tab/NativePageHandoffSource.java",\n'),
}

def transform(path, text):
    anchor, addition = ADDITIONS[path]
    if text.count(anchor) != 1:
        raise ValueError("Pinned Java registration anchor drift: " + path)
    counts = [text.count(entry) for entry in addition.splitlines(keepends=True)]
    if any(counts):
        if counts != [1] * len(counts) or addition + anchor not in text:
            raise ValueError("Partial/duplicate/moved Java registration: " + path)
        return text
    return text.replace(anchor, addition + anchor, 1)

def plan(root):
    root = Path(root)
    result = {root / path: transform(path, (root / path).read_text()) for path in ADDITIONS}
    base = Path(__file__).parent / "components"
    for destination, component in COMPONENTS.items():
        text = (base / component).read_text()
        path = root / destination
        if path.exists() and path.read_text() != text:
            raise ValueError("Refusing to replace different Java component: " + destination)
        result[path] = text
    return result
