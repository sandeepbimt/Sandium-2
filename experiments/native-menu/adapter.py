"""Held native-menu customization adapter. Not a CI hook or permission to build."""
from pathlib import Path
import hashlib, json, subprocess
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = 'chrome/browser/ui/android/appmenu/internal/'
JAVA = BASE + 'java/src/org/chromium/chrome/browser/ui/appmenu/'
HANDLER = JAVA + 'AppMenuHandlerImpl.java'
BUILD = BASE + 'BUILD.gn'
REVISION = '52bdd21723d5db0c9ab11716d38feac74828cf84'
SOURCES = ('RawSMenuModel.java', 'RawSMenuStore.java', 'RawSNativeMenu.java')

def once(text, before, after):
    if text.count(before) != 1: raise ValueError('Native menu hook changed: ' + before)
    return text.replace(before, after, 1)

def transform(path, text):
    if path == HANDLER:
        text = once(text, '    private final Context mContext;',
                    '    private final Context mContext;\n    private final RawSNativeMenu mRawSMenu;')
        text = once(text, '        mContext = context;',
                    '        mContext = context;\n        mRawSMenu = new RawSNativeMenu(context);')
        text = once(text, '        mModelList = mDelegate.getMenuItems();',
                    '        mModelList = mRawSMenu.prepare(mDelegate.getMenuItems());')
        text = once(text, '    void destroy() {',
                    '    void destroy() {\n        mRawSMenu.closeProjection();\n        mRawSMenu.dismissEditor();')
        text = once(text, '    public void onStopWithNative() {',
                    '    public void onStopWithNative() {\n        mRawSMenu.dismissEditor();')
        text = once(text, '    public void onConfigurationChanged(Configuration newConfig) {',
                    '    public void onConfigurationChanged(Configuration newConfig) {\n        mRawSMenu.dismissEditor();')
        text = once(text, '    public void appMenuDismissed() {',
                    '    public void appMenuDismissed() {\n        mRawSMenu.closeProjection();')
        anchor = '        mAppMenu.dismiss();\n\n        if (mTestOptionsItemSelectedListener != null) {'
        text = once(text, anchor, '        mAppMenu.dismiss();\n\n'
                    '        if (mRawSMenu.isEditor(model)) {\n'
                    '            mRawSMenu.showEditor();\n            return;\n        }\n\n'
                    '        if (mTestOptionsItemSelectedListener != null) {')
        return text
    if path == BUILD:
        anchor = '    "java/src/org/chromium/chrome/browser/ui/appmenu/AppMenu.java",'
        text = once(text, anchor, anchor + '\n' + '\n'.join(
            '    "java/src/org/chromium/chrome/browser/ui/appmenu/' + name + '",' for name in SOURCES))
        text = once(text, '    "java/res/values/dimens.xml",',
                    '    "java/res/values/dimens.xml",\n    "java/res/values/raws_menu.xml",\n    "java/res/values-hi/raws_menu.xml",')
        return text
    raise ValueError('Unreviewed path')

def plan(source):
    source = Path(source)
    if (source/'.git').exists() and subprocess.check_output(
            ['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() != REVISION:
        raise ValueError('Wrong Chromium revision')
    provenance = json.loads((HERE/'provenance.json').read_text())
    result = {}
    for path in (HANDLER, BUILD):
        original = (HERE/'fixtures'/Path(path).name).read_text()
        if hashlib.sha256(original.encode()).hexdigest() != provenance['sha256'][Path(path).name]:
            raise ValueError('Fixture changed')
        expected = transform(path, original)
        if (source/path).read_text() not in (original, expected):
            raise ValueError('Unreviewed native menu source: ' + path)
        result[source/path] = expected
    for name in SOURCES:
        result[source/JAVA/name] = (ROOT/'sandium/menu/java/org/chromium/chrome/browser/ui/appmenu'/name).read_text()
    result[source/BASE/'java/res/values/raws_menu.xml'] = (ROOT/'sandium/menu/raws_menu.xml').read_text()
    result[source/BASE/'java/res/values-hi/raws_menu.xml'] = (ROOT/'sandium/menu/raws_menu_hi.xml').read_text()
    for path, expected in result.items():
        if path not in (source/HANDLER, source/BUILD) and path.exists() and path.read_text() != expected:
            raise ValueError('Existing unreviewed module: ' + str(path))
    return result

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    changes = plan(args.source)
    if args.apply:
        for path, content in changes.items():
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)
    print('Reviewed native menu files:', len(changes), 'applied:', args.apply)
