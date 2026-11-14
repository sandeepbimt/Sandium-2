#!/usr/bin/env python3
"""Original Sandium menu presenter, applied only to the audited pinned Android source."""
from pathlib import Path
import argparse
import subprocess
import re
import xml.etree.ElementTree as ET

BRAVE_PIN = '44a84b1f89d9a35287289d6a3d493e362f5a5123'
CHROMIUM_PIN = 'd331de35ca8ab1358c7a17e4bd41627d55eaef51'
PACKAGE = 'org/chromium/chrome/browser/ui/appmenu/'
INTERNAL = 'chrome/browser/ui/android/appmenu/internal/'
PUBLIC = 'chrome/browser/ui/android/appmenu/'
CUSTOMIZE = 'browser/customize_menu/android/java/src/org/chromium/brave/browser/customize_menu/CustomizeBraveMenu.java'


def once(text, old, new):
    if new in text:
        return text
    if text.count(old) != 1:
        raise ValueError('Pinned menu anchor mismatch: ' + old[:100])
    return text.replace(old, new, 1)


def appmenu(text):
    if 'SANDIUM_PAGED_MENU_V1' in text and 'menu.setNativeDrillDown(' not in text:
        raise ValueError('Older unpublished menu draft detected; restore pinned AppMenu.java before applying this revision')
    text = once(text, '    private @Nullable Context mContext;', '''    private @Nullable org.chromium.ui.modelutil.MVCListAdapter.ModelList mSandiumModels;
    private @Nullable SandiumPagedMenu mSandiumMenu;
    void setSandiumModels(@Nullable org.chromium.ui.modelutil.MVCListAdapter.ModelList models) {
        mSandiumModels = models;
    }
    private @Nullable Context mContext;''')
    text = once(text, '                    mAdapter = null;', '                    mSandiumMenu = null;\n                    mSandiumModels = null;\n                    mAdapter = null;')
    text = once(text, '        popup.setContentView(contentView);', '''        // SANDIUM_PAGED_MENU_V1: preserve native list and dispatch for complex/conditional rows.
        if (mSandiumModels != null && context.getResources().getConfiguration().smallestScreenWidthDp < 600) {
            SandiumPagedMenu menu = new SandiumPagedMenu(context, mSandiumModels, contentView, mListView, footer);
            mSandiumMenu = menu;
            menu.setNativeDrillDown(mHierarchicalMenuController::shouldUseDrillDown);
            menu.setNativeReset(() -> {
                for (int depth = 0; depth < 64 && mHierarchicalMenuController.handleBackPress(); depth++) {}
            });
            int inset = Math.round(8 * context.getResources().getDisplayMetrics().density);
            int width = Math.max(1, visibleDisplayFrame.width() - 2 * inset);
            int available = Math.max(1, visibleDisplayFrame.height() - 2 * inset);
            int height = menu.preferredHeight(available);
            int x = visibleDisplayFrame.left + inset;
            popup.setWidth(width);
            popup.setHeight(height);
            popupPosition[0] = x;
            popupPosition[1] = visibleDisplayFrame.bottom - inset - height;
            menu.setResizeListener(() -> {
                if (!popup.isShowing()) return;
                int nextHeight = menu.preferredHeight(available);
                popup.update(x, visibleDisplayFrame.bottom - inset - nextHeight, width, nextHeight);
            });
            // Avoid the anchored zoom/slide on the custom bottom sheet. Keep
            // native popup lifecycle/dismissal, including outside-tap and Back.
            popup.setAnimationStyle(SysUtils.isLowEndDevice()
                    || !ValueAnimator.areAnimatorsEnabled() ? 0 : R.style.PopupWindowAnimFade);
            contentView = menu;
        }
        popup.setContentView(contentView);''')
    text = once(text, '                contentView, this::dismiss);', '''                contentView, () -> {
                    if (mSandiumMenu == null || !mSandiumMenu.handleBack()) dismiss();
                });''')
    text = once(text, '    public void updateMenuHeightWithAnimation() {', '''    public void updateMenuHeightWithAnimation() {
        if (mSandiumMenu != null) {
            mSandiumMenu.refresh();
            return;
        }''')
    return text


def handler(text):
    return once(text, '        mAppMenu.show(\n', '        mAppMenu.setSandiumModels(mModelList);\n        mAppMenu.show(\n')


def customize(text):
    if 'public static boolean isRemovedBySandium' not in text:
        raise ValueError('Apply Sandium UI product restrictions before paged menu')
    text = once(text, '            // Skip current item if it matches the customize menu id or settings menu id.', '''            if (BRAVE_CUSTOMIZE_ITEM_ID == menuItemId
                    && resources.getConfiguration().smallestScreenWidthDp < 600) {
                it.remove(); // The phone presenter owns transactional layout editing through +.
                continue;
            }
            // Skip current item if it matches the customize menu id or settings menu id.''')
    return once(text, '            if (!isVisible(resources, menuItemId)) {', '''            org.chromium.chrome.browser.ui.appmenu.SandiumMenuMetadata.record(
                    item.model, isVisible(resources, menuItemId));
            // Preserve product restrictions; only user-hidden shortcuts enter the phone editor.
            if (isRemovedBySandium(resources, menuItemId)
                    || (resources.getConfiguration().smallestScreenWidthDp >= 600
                            && !isVisible(resources, menuItemId))) {''')


def activity(text):
    return once(text, '''        if (currentTab == null) {
            return false;
        } else if (id == R.id.exit_id) {
            exitBrave();
        } else if (id == R.id.brave_rewards_id) {''', '''        if (id == R.id.exit_id) {
            // Exit needs no page, but keeps the existing native confirmation.
            exitBrave();
        } else if (currentTab == null) {
            return false;
        } else if (id == R.id.brave_rewards_id) {''')


def footer(text):
    text = once(text, 'implements View.OnClickListener {',
        'implements View.OnClickListener, org.chromium.chrome.browser.ui.appmenu.SandiumMenuMetadata.FooterProvider {')
    text = once(text, '    public void loadingStateChanged(boolean isLoading) {', '''    public void loadingStateChanged(boolean isLoading) {
        org.chromium.chrome.browser.ui.appmenu.SandiumMenuMetadata.footerChanged(this);''')
    return once(text, '    private AppMenuHandler mAppMenuHandler;', r'''    public org.chromium.ui.modelutil.MVCListAdapter.ModelList sandiumActions() {
        org.chromium.ui.modelutil.MVCListAdapter.ModelList actions =
                new org.chromium.ui.modelutil.MVCListAdapter.ModelList();
        for (MaterialButton button : new MaterialButton[] {
                mForwardButton, mBookmarkButton, mDownloadButton, mShareButton, mHomeButton, mReloadButton}) {
            if (button == null || button.getVisibility() != View.VISIBLE) continue;
            if (button.getParent() instanceof View
                    && ((View) button.getParent()).getVisibility() != View.VISIBLE) continue;
            org.chromium.ui.modelutil.PropertyModel model =
                    new org.chromium.ui.modelutil.PropertyModel.Builder(
                            org.chromium.chrome.browser.ui.appmenu.AppMenuItemProperties.ALL_KEYS)
                    .with(org.chromium.chrome.browser.ui.appmenu.AppMenuItemProperties.MENU_ITEM_ID, button.getId())
                    .with(org.chromium.chrome.browser.ui.appmenu.AppMenuItemProperties.TITLE, button.getContentDescription())
                    .with(org.chromium.chrome.browser.ui.appmenu.AppMenuItemProperties.ICON, button.getIcon())
                    .with(org.chromium.chrome.browser.ui.appmenu.AppMenuItemProperties.ENABLED, button.isEnabled())
                    .with(org.chromium.chrome.browser.ui.appmenu.AppMenuItemProperties.CHECKABLE, button.isCheckable())
                    .with(org.chromium.chrome.browser.ui.appmenu.AppMenuItemProperties.CHECKED, button.isChecked())
                    .build();
            org.chromium.chrome.browser.ui.appmenu.SandiumMenuMetadata.action(model, () -> {
                if (button.isEnabled()) button.performClick();
            });
            actions.add(new org.chromium.ui.modelutil.MVCListAdapter.ListItem(
                    org.chromium.chrome.browser.ui.appmenu.AppMenuHandler.AppMenuItemType.STANDARD, model));
        }
        return actions;
    }
    private AppMenuHandler mAppMenuHandler;''')


def register(text, names):
    anchor = '  sources = [\n'
    entries = ''.join('    "java/src/' + PACKAGE + name + '.java",\n' for name in names)
    start = text.index('android_library("java") {')
    end = text.index('\n}', start)
    return text[:start] + once(text[start:end], anchor, anchor + entries) + text[end:]


def register_resources(text):
    if 'java/res/values/sandium_menu_strings.xml' in text and 'java/res/values/sandium_menu_colors.xml' not in text:
        raise ValueError('Older unpublished menu resource registration detected; restore pinned appmenu internal BUILD.gn')
    start = text.index('android_resources("java_resources") {')
    end = text.index('\n}', start)
    anchor = '  sources = [\n'
    changed = once(text[start:end], anchor, anchor + '    "java/res/values/sandium_menu_strings.xml",\n    "java/res/values/sandium_menu_colors.xml",\n    "java/res/values-night/sandium_menu_colors.xml",\n')
    return text[:start] + changed + text[end:]


def apply(src, repo, verify_pin=True):
    core = src / 'brave'
    if verify_pin:
        for path, pin in [(src, CHROMIUM_PIN), (core, BRAVE_PIN)]:
            actual = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
            if actual != pin:
                raise ValueError('Source pin mismatch: ' + str(path))
    edits = {
        src / INTERNAL / ('java/src/' + PACKAGE + 'AppMenu.java'): appmenu,
        src / INTERNAL / ('java/src/' + PACKAGE + 'AppMenuHandlerImpl.java'): handler,
        core / CUSTOMIZE: customize,
        core / 'android/java/org/chromium/chrome/browser/app/appmenu/AppMenuIconRowFooter.java': footer,
        core / 'android/java/org/chromium/chrome/browser/app/BraveActivity.java': activity,
        src / INTERNAL / 'BUILD.gn': lambda t: register_resources(register(t, ['SandiumPagedMenu', 'SandiumMenuState'])),
        src / PUBLIC / 'BUILD.gn': lambda t: register(t, ['SandiumMenuMetadata']),
    }
    # Validate every transformation before mutating any source file.
    updated = {path: transform(path.read_text()) for path, transform in edits.items()}
    for path, text in updated.items():
        path.write_text(text)
    strings = src / INTERNAL / 'java/res/values/sandium_menu_strings.xml'
    strings.parent.mkdir(parents=True, exist_ok=True)
    strings.write_text((repo / 'android/java/res/values/sandium_menu_strings.xml').read_text())
    for qualifier in ['values', 'values-night']:
        relative = 'java/res/' + qualifier + '/sandium_menu_colors.xml'
        color = src / INTERNAL / relative
        color.parent.mkdir(parents=True, exist_ok=True)
        color.write_bytes((repo / 'android' / relative).read_bytes())
    for name, base in [('SandiumMenuState', INTERNAL), ('SandiumPagedMenu', INTERNAL), ('SandiumMenuMetadata', PUBLIC)]:
        dest = src / base / ('java/src/' + PACKAGE + name + '.java')
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text((repo / 'android/java' / PACKAGE / (name + '.java')).read_text())


def verify(src, repo, verify_pin=True):
    """Read-only contract check against real restored/applied source; no external fixtures."""
    core = src / 'brave'
    if verify_pin:
        for path, pin in [(src, CHROMIUM_PIN), (core, BRAVE_PIN)]:
            actual = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
            if actual != pin:
                raise ValueError('Source pin mismatch: ' + str(path))
    transforms = {
        src / INTERNAL / ('java/src/' + PACKAGE + 'AppMenu.java'): appmenu,
        src / INTERNAL / ('java/src/' + PACKAGE + 'AppMenuHandlerImpl.java'): handler,
        core / CUSTOMIZE: customize,
        core / 'android/java/org/chromium/chrome/browser/app/appmenu/AppMenuIconRowFooter.java': footer,
        core / 'android/java/org/chromium/chrome/browser/app/BraveActivity.java': activity,
        src / INTERNAL / 'BUILD.gn': lambda t: register_resources(register(t, ['SandiumPagedMenu', 'SandiumMenuState'])),
        src / PUBLIC / 'BUILD.gn': lambda t: register(t, ['SandiumMenuMetadata']),
    }
    for path, transform in transforms.items():
        current = path.read_text()
        if transform(current) != current:
            raise ValueError('Menu contract not applied: ' + str(path))
    for name, base in [('SandiumMenuState', INTERNAL), ('SandiumPagedMenu', INTERNAL), ('SandiumMenuMetadata', PUBLIC)]:
        dest = src / base / ('java/src/' + PACKAGE + name + '.java')
        if dest.read_bytes() != (repo / 'android/java' / PACKAGE / (name + '.java')).read_bytes():
            raise ValueError('Menu Java drift: ' + str(dest))
        entry = '"java/src/' + PACKAGE + name + '.java"'
        if (src / base / 'BUILD.gn').read_text().count(entry) != 1:
            raise ValueError('Menu GN entry missing/duplicated: ' + name)
    resource = src / INTERNAL / 'java/res/values/sandium_menu_strings.xml'
    if resource.read_bytes() != (repo / 'android/java/res/values/sandium_menu_strings.xml').read_bytes():
        raise ValueError('Menu strings drift')
    if (src / INTERNAL / 'BUILD.gn').read_text().count('"java/res/values/sandium_menu_strings.xml"') != 1:
        raise ValueError('Menu strings GN registration missing/duplicated')
    color_names = set()
    for qualifier in ['values', 'values-night']:
        relative = 'java/res/' + qualifier + '/sandium_menu_colors.xml'
        color = src / INTERNAL / relative
        if color.read_bytes() != (repo / 'android' / relative).read_bytes():
            raise ValueError('Menu colors drift: ' + qualifier)
        if (src / INTERNAL / 'BUILD.gn').read_text().count('"' + relative + '"') != 1:
            raise ValueError('Menu color GN registration missing/duplicated: ' + qualifier)
        color_names.update(node.get('name') for node in ET.parse(color).getroot())
    names = [node.get('name') for node in ET.parse(resource).getroot()]
    if len(names) != len(set(names)):
        raise ValueError('Duplicate menu resource names')
    java = (src / INTERNAL / ('java/src/' + PACKAGE + 'SandiumPagedMenu.java')).read_text()
    missing_colors = set(re.findall(r'R\.color\.(sandium_menu_[a-z_]+)', java)) - color_names
    if missing_colors:
        raise ValueError('Missing menu colors: ' + repr(missing_colors))
    missing = set(re.findall(r'R\.string\.(sandium_menu_[a-z_]+)', java)) - set(names)
    if missing:
        raise ValueError('Missing menu resources: ' + repr(missing))
    print('SANDIUM_PAGED_MENU_CONTRACT=PASS (source/resources only, not Android runtime validation)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('src', type=Path)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    if not args.verify_only:
        apply(args.src, args.repo)
    verify(args.src, args.repo)
