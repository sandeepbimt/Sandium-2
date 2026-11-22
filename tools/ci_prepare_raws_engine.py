"""Stage the exact Brave source slice in worker scratch; no cache output."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'raws-adblock'))
import stage
from ci_timing import prep_phase
from restore_only_menu_ui import (
    MENU_PARITY_TRACKED, MENU_PARITY_JAVA, MENU_PARITY_RESOURCES,
)

URL = 'https://github.com/brave/brave-core.git'
BRAVE_PIN = 'bd6d26d1bced03c17a98baa86d2cd3425d543d1b'

def stage_from_checkout(repo):
    if stage.PINS['brave_core'] != BRAVE_PIN:
        raise ValueError('Reviewed Brave checkout pin changed')
    stage.git(repo, 'cat-file', '-e', BRAVE_PIN+'^{commit}')
    stage.prepare(repo, ROOT/'.raws-staged-engine', BRAVE_PIN)

def prepare():
    """Fetch fixed trusted provider; only run after exact restore/budget checks."""
    if (ROOT/'.raws-staged-engine').exists() or (ROOT/'.raws-staged-engine').is_symlink():
        raise ValueError('Refusing pre-existing staged RawS engine source')
    with tempfile.TemporaryDirectory(prefix='raws-engine-source-') as tmp:
        repo=Path(tmp)/'input.git'
        with prep_phase('brave-pinned-fetch'):
            subprocess.run(['git','init','--bare',str(repo)],check=True,timeout=20)
            env=dict(os.environ,GIT_TERMINAL_PROMPT='0')
            subprocess.run(['git','-C',str(repo),'-c','protocol.version=2','fetch','--no-tags',
                            '--depth=1',URL,BRAVE_PIN],
                           check=True,env=env,timeout=240)
            if stage.git(repo,'rev-parse','FETCH_HEAD').decode().strip() != BRAVE_PIN:
                raise ValueError('Wrong fetched Brave pin')
        with prep_phase('brave-extract-pinned-slice'):
            stage_from_checkout(repo)

def ui_source_targets():
    main = '//chrome/android'
    app_java = main + '/java/src/org/chromium/chrome/browser'
    appmenu = '//chrome/browser/ui/android/appmenu'
    internal = appmenu + '/internal'
    toolbar = '//chrome/browser/ui/android/toolbar'
    feed = '//chrome/browser/feed/android'
    # Chromium's base manifest resources and public APK branding overlay own
    # these files; they are not sources of chrome_app_java_resources itself.
    public_branding = {
        main+'/java/res_chromium_base/values/channel_constants.xml',
        *(main+'/java/res_chromium_base/mipmap-'+dpi+'/'+name
          for dpi in ('mdpi', 'hdpi', 'xhdpi', 'xxhdpi', 'xxxhdpi')
          for name in ('app_icon.png', 'layered_app_icon.png')),
    }
    targets = {
        '//chrome/browser/ui/android/omnibox:java__compile_java': ('inputs', {
            '//chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/OmniboxSuggestionsDropdownEmbedderImpl.java',
            '//chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/GroupSeparatorDecoration.java',
            '//chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/HeaderDecoration.java',
            '//chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsContainer.java',
            '//chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsDropdown.java',
            '//chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsDropdownEmbedder.java',
            '//chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/SuggestionHorizontalDivider.java',
            '//chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/base/BaseSuggestionView.java',
        }),
        main+':chrome_jni_headers__action': ('inputs', {
            app_java+'/settings/RawsProtectionCopy.java',
        }),
        main+':chrome_base_module_resources__prepare': ('sources', public_branding | {
            main+'/java/res_base/drawable/ic_launcher.xml',
            main+'/java/res_base/drawable/ic_launcher_round.xml',
        }),
        main+':chrome_public_apk_base_module_resources__prepare': ('sources', public_branding),
        main+':new_tab_page_utils_java__compile_java': ('inputs', {
            app_java+'/ntp/NewTabPageUtils.java',
        }),
        feed+':java__compile_java': ('inputs', {
            feed+'/java/src/org/chromium/chrome/browser/feed/FeedFeatures.java',
        }),
        # Chromium 52bdd217: android_library() exposes a group with no files.
        # internal_rules.gni:3067,4161 attach Java paths as javac action inputs.
        main+':chrome_java__compile_java': ('inputs', {
            main+'/feed/core/java/src/org/chromium/chrome/browser/feed/FeedSurfaceCoordinator.java',
        } | {app_java+'/'+name for name in (
            'ChromeTabbedActivity.java', 'tabbed_mode/TabbedAppMenuPropertiesDelegate.java',
            'ntp/NewTabPageCoordinator.java', 'ntp/NewTabPage.java',
            'toolbar/ToolbarManager.java',
            'appearance/settings/AppearanceSettingsFragment.java',
            'suggestions/tile/MostVisitedTilesLayout.java',
            'suggestions/tile/SuggestionsTileView.java',
            'signin/SigninFirstRunFragment.java', 'settings/MainSettings.java',
            'sync/settings/SignInPreference.java',
            'settings/RawsGlobalShieldSheet.java', 'settings/SandiumBalancedTracer.java',
            'settings/RawsProtectionSettings.java',
            'settings/RawsProtectionCopy.java')}),
        # rules.gni:833 and internal_rules.gni:2042 forward resources into
        # the __prepare action's sources, not the public group.
        main+':chrome_app_java_resources__prepare': ('sources', {main+'/java/res/'+name for name in (
            'values/raws_main_settings_palette.xml', 'values-night/raws_main_settings_palette.xml',
            'values/raws_main_settings_strings.xml', 'xml/main_preferences.xml',
            'xml/appearance_preferences.xml',
            'values/raws_welcome_palette.xml', 'values-night/raws_welcome_palette.xml',
            'drawable/raws_global_shield_icon.xml', 'layout/raws_global_shield_sheet.xml',
            'values/raws_global_shield_strings.xml', 'xml/raws_protection_preferences.xml',
            'drawable-nodpi/raws_frozen_shields_mark.webp',
            'drawable-nodpi/raws_home_wallpaper.webp',
            'drawable/raws_frozen_shields_card.xml',
            'drawable/raws_frozen_shields_dns_picker.xml',
            'drawable/raws_frozen_shields_rim.xml',
        )}),
        appmenu+':java__compile_java': ('inputs', {
            appmenu+'/java/src/org/chromium/chrome/browser/ui/appmenu/'+name
            for name in ('AppMenuHandler.java', 'AppMenuPropertiesDelegate.java')}),
        internal+':java__compile_java': ('inputs', {internal+'/java/src/org/chromium/chrome/browser/ui/appmenu/'+name
                           for name in ('AppMenuHandlerImpl.java', 'AppMenuDragHelper.java', 'RawSNativeMenu.java',
                                        'RawSMenuModel.java', 'RawSMenuStore.java')}
                                 | {'//' + path for path in MENU_PARITY_TRACKED | MENU_PARITY_JAVA}),
        internal+':java_resources__prepare': ('sources', {internal+'/java/res/'+name for name in (
            'values/raws_menu.xml', 'values-hi/raws_menu.xml')}
                                      | {'//' + path for path in MENU_PARITY_RESOURCES}),
        '//chrome/browser/ui/android/bottombar:config_java__compile_java': ('inputs', {
            '//chrome/browser/ui/android/bottombar/java/src/org/chromium/chrome/'
            'browser/ui/bottombar/BottomBarConfigUtils.java',
        }),
        toolbar+':java_resources__prepare': ('sources', {
            toolbar+'/java/res/layout/toolbar_phone.xml',
            toolbar+'/java/res/drawable/raws_page_toolbar_forward.xml',
            toolbar+'/java/res/drawable/raws_page_toolbar_menu.xml',
            toolbar+'/java/res/values/raws_address_controls.xml',
        }),
        toolbar+':core_java__compile_java': ('inputs', {
            *(toolbar+'/java/src/org/chromium/chrome/browser/toolbar/top/'+name for name in (
                'ToggleTabStackButton.java', 'ToggleTabStackButtonCoordinator.java',
                'TopToolbarOverlayMediator.java')),

            toolbar+'/java/src/org/chromium/chrome/browser/toolbar/top/ToolbarPhone.java',
            toolbar+'/java/src/org/chromium/chrome/browser/toolbar/menu_button/MenuButton.java',
            toolbar+'/java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java',
            toolbar+'/java/src/org/chromium/chrome/browser/toolbar/settings/AddressBarPreference.java',
        }),
    }

    parity = __import__('json').loads((ROOT/'tools/frozen_android_owners.json').read_text())
    for label,(field,paths) in parity.items():
        if label in targets and targets[label][0] != field:
            raise ValueError('Source-owner field mismatch: '+label)
        targets.setdefault(label, (field, set()))[1].update(paths)
    return targets


def verify_apk_graph(src, gn, out, env, artifact, *, require_ui=False):
    def describe(label, field, *flags):
        return subprocess.check_output([str(gn), 'desc', str(out), label, field, *flags],
                                       cwd=src,env=env,text=True,timeout=120)
    graph=describe('//chrome/android:chrome_public_apk','deps','--all')
    lines={line.strip() for line in graph.splitlines()}
    # Preserve the engine-only verifier's existing handling of dependencies.
    labels={line.split('(',1)[0].rstrip() for line in lines}
    required={'//components/sandium_adblock:document_subresource_factory',
        '//brave/third_party/rust/adblock/v0_13:lib',
        '//chrome/browser:resources'}
    if not required <= labels:
        raise ValueError('APK graph lacks RawS engine or assets: '+str(sorted(required-labels)))
    verified='verified labels:\n'+'\n'.join(sorted(required))+'\n'
    if require_ui:
        ui_targets=ui_source_targets()
        # GN omits the suffix for the default toolchain; an explicitly
        # toolchain-qualified host/secondary action is not APK linkage proof.
        if not ui_targets.keys() <= lines:
            raise ValueError('APK graph lacks RawS UI actions: '+str(sorted(ui_targets.keys()-lines)))
        checked=set()
        for label, (field, paths) in ui_targets.items():
            actual={line.strip() for line in describe(label,field).splitlines()}
            if not paths <= actual:
                raise ValueError('APK graph lacks RawS UI sources: '+str(sorted(paths-actual)))
            checked.update(paths)
        direct_linkage = {
            '//chrome/android:chrome_java':'//chrome/android:chrome_app_java_resources',
            '//chrome/browser/ui/android/toolbar:core_java':
                '//chrome/browser/ui/android/toolbar:java_resources',
            '//chrome/browser/ui/android/appmenu/internal:java':
                '//chrome/browser/ui/android/appmenu/internal:java_resources',
        }
        for java, resources in direct_linkage.items():
            java_deps={line.strip() for line in describe(java,'deps').splitlines()}
            if resources not in java_deps:
                raise ValueError('APK graph lacks RawS UI resource dependency: '+resources)
        verified+='verified UI actions:\n'+'\n'.join(sorted(ui_targets))+'\n'
        verified+='verified UI sources:\n'+'\n'.join(sorted(checked))+'\n'
    artifact.write_text(verified)

def run_native_gate(src, artifacts, env, budget, *, port1442=False):
    from ci_remote import run_logged
    import json
    if budget < 120:
        raise ValueError('Insufficient time to verify the actual RawS engine')
    before=set((src/'out').glob('RawSHostSmoke-*'))
    # Reuse the fresh, rehashed staged closure captured from reviewed Git objects.
    # Do not re-fetch or publish cache; keep one log and the exact test receipt.
    flag = ['--port1442'] if port1442 else []
    run_logged(['timeout','--kill-after=20s',str(budget),sys.executable,
                str(ROOT/'raws-adblock/native_smoke.py'),'--src',str(src),
                '--verified-staged-tree',str(ROOT/'.raws-staged-engine'),*flag],
               artifacts/'raws-engine-host-smoke.log',phase='raws-engine-host-smoke',
               cwd=ROOT,env=env,check=True)
    new=set((src/'out').glob('RawSHostSmoke-*'))-before
    if len(new)!=1:
        raise ValueError('Ambiguous newly generated native test receipt')
    result=(new.pop()/'engine-result.json').read_bytes()
    value=json.loads(result)
    cases = value.get('cases', [])
    if (len(cases) != (14 if port1442 else 9)
            or ('incident1471-player-rules' in cases) != port1442
            or value.get('apk_tested') is not False):
        raise ValueError('Incomplete real native smoke test')
    (artifacts/'raws-engine-host-result.json').write_bytes(result)
    return value

if __name__ == '__main__':
    prepare()
