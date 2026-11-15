#!/usr/bin/env python3
"""Settings-owned transitions only; preserve native navigation and animation type."""
import argparse
import importlib.util
from pathlib import Path
import subprocess

CHROMIUM_PIN = 'd331de35ca8ab1358c7a17e4bd41627d55eaef51'
BRAVE_PIN = '44a84b1f89d9a35287289d6a3d493e362f5a5123'
SETTINGS = 'chrome/android/java/src/org/chromium/chrome/browser/settings/SettingsActivity.java'
BRAVE_SETTINGS = 'android/java/org/chromium/chrome/browser/settings/BraveSettingsActivity.java'
MARK = 'SANDIUM_SETTINGS_FADE_V1'

def once(s, old, new):
    if s.count(old) != 1: raise ValueError('Pinned Settings fade anchor changed: ' + old[:80])
    return s.replace(old, new, 1)

def settings(s):
    if MARK in s: return s
    anchor = '    private static void setFragmentAnimation(FragmentTransaction transaction, Fragment fragment) {\n'
    s = once(s, anchor, anchor + '        // SANDIUM_SETTINGS_FADE_V1: retain TWEEN/PROPERTY ownership and native back stack.\n        if (!android.animation.ValueAnimator.areAnimatorsEnabled()) {\n            transaction.setCustomAnimations(0, 0, 0, 0);\n            return;\n        }\n')
    # Only this Settings transaction owns these references. No global X-axis resources change.
    for kind in ('anim', 'animator'):
        for direction in ('open', 'close'):
            for phase in ('enter', 'exit'):
                old = f'R.{kind}.shared_x_axis_{direction}_{phase}'
                s = once(s, old, f'R.{kind}.sandium_settings_fade_{"in" if phase == "enter" else "out"}')
    return s

def brave(s):
    if MARK in s: return s
    # Remove prior view alpha hook: transaction/window now owns motion without double fading.
    spec = importlib.util.spec_from_file_location('native_theme', Path(__file__).with_name('apply-sandium-native-theme.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    callback = '                    view.post(() -> onSettingsFragmentViewReady(fragment, view));'
    expanded = module.settings_motion(callback)
    s = once(s, expanded, callback)
    s = once(s, '        super.onCreate(savedInstanceState);', '        super.onCreate(savedInstanceState);\n        // Activity boundary, including standalone subpages. Fragment motion is owned separately.\n        if (android.os.Build.VERSION.SDK_INT >= 34) {\n            sandiumConfigureWindowFade();\n        } else if (savedInstanceState == null) {\n            overridePendingTransition(sandiumFadeIn(), sandiumFadeOut());\n        }')
    # Native close action reorders the browser rather than finishing Settings.
    s = once(s, '            startActivity(intent);\n            return true;', '            startActivity(intent);\n            overridePendingTransition(sandiumFadeIn(), sandiumFadeOut());\n            return true;')
    anchor = '    @Override\n    protected void onDestroy() {'
    s = once(s, anchor, '    // SANDIUM_SETTINGS_FADE_V1: no delayed finish, input lock, or custom back handling.\n    private int sandiumFadeIn() {\n        return android.animation.ValueAnimator.areAnimatorsEnabled()\n                ? R.anim.sandium_settings_fade_in : 0;\n    }\n\n    private int sandiumFadeOut() {\n        return android.animation.ValueAnimator.areAnimatorsEnabled()\n                ? R.anim.sandium_settings_fade_out : 0;\n    }\n\n    @android.annotation.TargetApi(34)\n    private void sandiumConfigureWindowFade() {\n        overrideActivityTransition(OVERRIDE_TRANSITION_OPEN, sandiumFadeIn(), sandiumFadeOut());\n        overrideActivityTransition(OVERRIDE_TRANSITION_CLOSE, sandiumFadeIn(), sandiumFadeOut());\n    }\n\n    @Override\n    public void finish() {\n        if (android.os.Build.VERSION.SDK_INT >= 34) sandiumConfigureWindowFade();\n        super.finish();\n        if (android.os.Build.VERSION.SDK_INT < 34) {\n            overridePendingTransition(sandiumFadeIn(), sandiumFadeOut());\n        }\n    }\n\n' + anchor)
    return s

def resources():
    result = {}
    for kind in ('anim', 'animator'):
        for phase, start, end, ms in [('in', 0, 1, 100), ('out', 1, 0, 80)]:
            if kind == 'anim':
                body = f'<alpha xmlns:android="http://schemas.android.com/apk/res/android" android:fromAlpha="{start}" android:toAlpha="{end}" android:duration="{ms}" android:interpolator="@android:interpolator/linear" />\n'
            else:
                body = f'<objectAnimator xmlns:android="http://schemas.android.com/apk/res/android" android:propertyName="alpha" android:valueFrom="{start}" android:valueTo="{end}" android:valueType="floatType" android:duration="{ms}" android:interpolator="@android:interpolator/linear" />\n'
            result[f'android/java/brave-res/{kind}/sandium_settings_fade_{phase}.xml'] = '<?xml version="1.0" encoding="utf-8"?>\n' + body
    return result

def build(s):
    for name in resources():
        relative = name.removeprefix('android/')
        if f'"{relative}"' not in s:
            s = once(s, 'android_resources("java_resources") {\n  sources = [', 'android_resources("java_resources") {\n  sources = [\n    "' + relative + '",')
    return s

def apply(src, core, verify=False):
    for root, pin in ((src, CHROMIUM_PIN), (core, BRAVE_PIN)):
        if subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip() != pin:
            raise ValueError('Unexpected pin')
    outputs = {src/SETTINGS: settings((src/SETTINGS).read_text()),
               core/BRAVE_SETTINGS: brave((core/BRAVE_SETTINGS).read_text()),
               core/'android/BUILD.gn': build((core/'android/BUILD.gn').read_text())}
    outputs.update({core/p: text for p, text in resources().items()})
    for p, out in outputs.items():
        if verify:
            if not p.exists() or p.read_text() != out: raise ValueError('Missing Settings fade: ' + str(p))
        else:
            p.parent.mkdir(parents=True, exist_ok=True); p.write_text(out)

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--src',type=Path,required=True); p.add_argument('--core',type=Path,required=True); p.add_argument('--verify-only',action='store_true')
    a=p.parse_args(); apply(a.src,a.core,a.verify_only)
