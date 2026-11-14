#!/usr/bin/env python3
"""Source-shape/idempotency tests, not a substitute for an Android compile/device test."""
import importlib.util
from pathlib import Path
import tempfile
import shutil
import argparse
import re
import xml.etree.ElementTree as ET


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def run(audit, chromium, repo):
    patch = load('menu_patch', repo / '.circleci/scripts/apply-sandium-paged-menu.py')
    prune = load('menu_prune', repo / '.circleci/scripts/apply-sandium-ui-prune.py')
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp); core = src / 'brave'
        files = {
            patch.INTERNAL + 'java/src/' + patch.PACKAGE + 'AppMenu.java': chromium / 'AppMenu.java',
            patch.INTERNAL + 'java/src/' + patch.PACKAGE + 'AppMenuHandlerImpl.java': chromium / 'AppMenuHandlerImpl.java',
            patch.INTERNAL + 'BUILD.gn': chromium / 'appmenu_internal_BUILD.gn',
            patch.PUBLIC + 'BUILD.gn': chromium / 'appmenu_BUILD.gn',
        }
        for destination, source in files.items():
            target = src / destination; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
        for relative in [patch.CUSTOMIZE,
                'android/java/org/chromium/chrome/browser/app/BraveActivity.java',
                'android/java/org/chromium/chrome/browser/app/appmenu/AppMenuIconRowFooter.java']:
            target = core / relative; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(audit / relative, target)
        prune.patch_customize_menu(core)
        patch.apply(src, repo, False)
        first = {str(p.relative_to(src)): p.read_bytes() for p in src.rglob('*') if p.is_file()}
        patch.apply(src, repo, False)
        patch.verify(src, repo, False)
        second = {str(p.relative_to(src)): p.read_bytes() for p in src.rglob('*') if p.is_file()}
        assert first == second, 'not idempotent'
        copy = src / patch.INTERNAL / ('java/src/' + patch.PACKAGE + 'SandiumMenuState.java')
        original = copy.read_bytes(); copy.write_bytes(original + b'\n// drift\n')
        try:
            patch.verify(src, repo, False)
        except ValueError as error:
            assert 'drift' in str(error)
        else:
            raise AssertionError('contract missed drift')
        copy.write_bytes(original)
        custom = (core / patch.CUSTOMIZE).read_text()
        assert 'if (isRemovedBySandium(resources, menuItemId)' in custom
        assert 'SandiumMenuMetadata.record' in custom
        java = (src / patch.INTERNAL / ('java/src/' + patch.PACKAGE + 'AppMenu.java')).read_text()
        assert java.index('contentView = menu;') < java.index('popup.setContentView(contentView);')
        assert 'smallestScreenWidthDp < 600' in java
        assert 'popup.update(x, visibleDisplayFrame.bottom - inset - nextHeight' in java
        assert 'exitBrave();' in (core / 'android/java/org/chromium/chrome/browser/app/BraveActivity.java').read_text()
    java_source = (repo / 'android/java' / patch.PACKAGE / 'SandiumPagedMenu.java').read_text()
    assert 'setBackground(shape(mPanelColor, 12));' in java_source
    resource_names = {e.get('name') for e in ET.parse(repo / 'android/java/res/values/sandium_menu_strings.xml').getroot()}
    required = set(re.findall(r'R\.string\.(sandium_menu_[a-z_]+)', java_source))
    assert required <= resource_names, required - resource_names
    assert 'mDraft == null || mDraft != editing' in java_source
    assert 'disableTree(tile)' in java_source
    assert 'listener != null && anchor.isEnabled()' in java_source
    assert 'uptimeMillis() >= mDeadline' in java_source
    assert 'postDelayed(mPendingNativeAction.mExpire, 500)' in java_source
    assert 'ACTION_DOWN) clearPendingNativeAction()' in java_source
    assert 'R.color.schemes_' not in java_source
    assert 'AppMenuItemViewBinder.bindStandardItem(iconModel, icon, AppMenuItemProperties.ICON)' in java_source
    for key in ['ICON_COLOR_RES', 'ICON_NO_TINT', 'ICON_SHOW_BADGE', 'ICON_SUPPLIER']:
        assert 'AppMenuItemProperties.' + key in java_source
    assert 'supplier.onAvailable(drawable -> model.set(AppMenuItemProperties.ICON, drawable))' in java_source
    assert 'mRequestedIcons.get(model) == supplier' in java_source
    print('Sandium paged-menu source transformation tests passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--chromium-fixtures', type=Path, required=True)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(); run(args.audit, args.chromium_fixtures, args.repo)
