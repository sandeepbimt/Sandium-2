"""Stage the exact Brave source slice in worker scratch; no cache output."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'raws-adblock'))
import stage

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
        subprocess.run(['git','init','--bare',str(repo)],check=True,timeout=20)
        env=dict(os.environ,GIT_TERMINAL_PROMPT='0')
        subprocess.run(['git','-C',str(repo),'-c','protocol.version=2','fetch','--no-tags',
                        '--depth=1',URL,BRAVE_PIN],
                       check=True,env=env,timeout=240)
        if stage.git(repo,'rev-parse','FETCH_HEAD').decode().strip() != BRAVE_PIN:
            raise ValueError('Wrong fetched Brave pin')
        stage_from_checkout(repo)

def ui_source_targets():
    main = '//chrome/android'
    app_java = main + '/java/src/org/chromium/chrome/browser'
    appmenu = '//chrome/browser/ui/android/appmenu'
    internal = appmenu + '/internal'
    toolbar = '//chrome/browser/ui/android/toolbar'
    return {
        # Chromium 52bdd217: android_library() exposes a group with no files.
        # internal_rules.gni:3067,4161 attach Java paths as javac action inputs.
        main+':chrome_java__compile_java': ('inputs', {app_java+'/'+name for name in (
            'ChromeTabbedActivity.java', 'tabbed_mode/TabbedAppMenuPropertiesDelegate.java',
            'signin/SigninFirstRunFragment.java', 'settings/MainSettings.java',
            'settings/RawsGlobalShieldSheet.java', 'settings/RawsProtectionSettings.java',
            'settings/RawsProtectionCopy.java')}),
        # rules.gni:833 and internal_rules.gni:2042 forward resources into
        # the __prepare action's sources, not the public group.
        main+':chrome_app_java_resources__prepare': ('sources', {main+'/java/res/'+name for name in (
            'values/raws_main_settings_palette.xml', 'values-night/raws_main_settings_palette.xml',
            'values/raws_main_settings_strings.xml', 'xml/main_preferences.xml',
            'values/raws_welcome_palette.xml', 'values-night/raws_welcome_palette.xml',
            'drawable/raws_global_shield_icon.xml', 'layout/raws_global_shield_sheet.xml',
            'values/raws_global_shield_strings.xml', 'xml/raws_protection_preferences.xml')}),
        appmenu+':java__compile_java': ('inputs', {
            appmenu+'/java/src/org/chromium/chrome/browser/ui/appmenu/'+name
            for name in ('AppMenuHandler.java', 'AppMenuPropertiesDelegate.java')}),
        internal+':java__compile_java': ('inputs', {internal+'/java/src/org/chromium/chrome/browser/ui/appmenu/'+name
                           for name in ('AppMenuHandlerImpl.java', 'RawSNativeMenu.java',
                                        'RawSMenuModel.java', 'RawSMenuStore.java')}),
        internal+':java_resources__prepare': ('sources', {internal+'/java/res/'+name for name in (
            'values/raws_menu.xml', 'values-hi/raws_menu.xml')}),
        toolbar+':core_java__compile_java': ('inputs', {
            toolbar+'/java/src/org/chromium/chrome/browser/toolbar/top/ToolbarPhone.java'}),
    }


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

def run_native_gate(src, artifacts, env, budget):
    from ci_remote import run_logged
    import json
    if budget < 120:
        raise ValueError('Insufficient time to verify the actual RawS engine')
    before=set((src/'out').glob('RawSHostSmoke-*'))
    # Reuse the fresh, rehashed staged closure captured from reviewed Git objects.
    # Do not re-fetch or publish cache; keep one log and the exact test receipt.
    run_logged(['timeout','--kill-after=20s',str(budget),sys.executable,
                str(ROOT/'raws-adblock/native_smoke.py'),'--src',str(src),
                '--verified-staged-tree',str(ROOT/'.raws-staged-engine')],
               artifacts/'raws-engine-host-smoke.log',phase='raws-engine-host-smoke',
               cwd=ROOT,env=env,check=True)
    new=set((src/'out').glob('RawSHostSmoke-*'))-before
    if len(new)!=1:
        raise ValueError('Ambiguous newly generated native test receipt')
    result=(new.pop()/'engine-result.json').read_bytes()
    value=json.loads(result)
    if len(value.get('cases',[]))!=9 or value.get('apk_tested') is not False:
        raise ValueError('Incomplete real native smoke test')
    (artifacts/'raws-engine-host-result.json').write_bytes(result)
    return value

if __name__ == '__main__':
    prepare()
