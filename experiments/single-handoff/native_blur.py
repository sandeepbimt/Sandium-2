"""Pinned Chromium156 blur, with separately named optional 20% dim only.

Run in outer journal after native-navigation reverses legacy customizations.
No custom capture, delay, sigma, fallback color or eligibility changes.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
HERE=Path(__file__).resolve().parent
FIX=HERE/'fixtures/native-blur-156'
MANIFEST=json.loads((FIX/'manifest.json').read_text())
PIN='d331de35ca8ab1358c7a17e4bd41627d55eaef51'
CC='content/browser/navigation_transitions/blur_transition_animation_manager.cc'
H=CC[:-2]+'h'
FC='content/public/common/content_features.cc'
FH=FC[:-2]+'h'
INPUTS={CC,H,FC,FH}

def fixture(path):
    item=MANIFEST['files'][path];data=(FIX/item['file']).read_bytes()
    if MANIFEST['pin']!=PIN or hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=item['git_blob']:
        raise ValueError('Native blur156 fixture integrity failed: '+path)
    return data.decode()

def once(s,a,b):
    if s.count(a)!=1:raise ValueError('Native blur156 anchor drift: '+a[:80])
    return s.replace(a,b,1)

def dim_cc(s):
    s=once(s,'#include "base/metrics/histogram_functions.h"', '#include "base/feature_list.h"\n#include "base/metrics/histogram_functions.h"')
    s=once(s,'namespace {\n','namespace {\n\n// Separate Sandium control; native blur parameters remain untouched.\nBASE_FEATURE(kSandiumNavigationTransitionDim, base::FEATURE_DISABLED_BY_DEFAULT);\n')
    a='  fallback_color_layer_->SetOpacity(0.0f);\n\n  SetAnimationState(AnimationState::kNone);'
    s=once(s,a,'''  fallback_color_layer_->SetOpacity(0.0f);
  if (base::FeatureList::IsEnabled(kSandiumNavigationTransitionDim)) {
    darken_layer_ = cc::slim::SolidColorLayer::Create();
    darken_layer_->SetIsDrawable(true);
    darken_layer_->SetBounds(native_view->GetPhysicalBackingSize());
    darken_layer_->SetBackgroundColor(SkColors::kBlack);
    darken_layer_->SetOpacity(0.20f);
  }

  SetAnimationState(AnimationState::kNone);''')
    a='''      if (fallback_color_layer_) {
        fallback_color_layer_->SetOpacity(initial_fallback_opacity_ *
                                          adjusted_opacity_multiplier);
      }'''
    s=once(s,a,a+'''
      if (darken_layer_) {
        darken_layer_->SetOpacity(initial_darken_opacity_ * adjusted_opacity_multiplier);
      }''')
    a='      // Drop the old page\'s surface now that it\'s completely covered.'
    s=once(s,a,'''      if (darken_layer_) {
        darken_layer_->RemoveFromParent();
        darken_layer_.reset();
      }
'''+a)
    a='''    if (fallback_color_layer_) {
      layer_tree->AddChild(fallback_color_layer_);
    }'''
    s=once(s,a,'''    if (darken_layer_) {
      layer_tree->AddChild(darken_layer_);
    }
'''+a)
    a='''  if (fallback_color_layer_ && fallback_color_layer_->parent()) {
    fallback_color_layer_->RemoveFromParent();
  }'''
    s=once(s,a,'''  if (darken_layer_ && darken_layer_->parent()) {
    darken_layer_->RemoveFromParent();
  }
'''+a)
    s=once(s,'  blur_layer_.reset();\n  fallback_color_layer_.reset();','  blur_layer_.reset();\n  darken_layer_.reset();\n  fallback_color_layer_.reset();')
    a='''  initial_fallback_opacity_ =
      fallback_color_layer_ ? fallback_color_layer_->opacity() : 0.0f;'''
    return once(s,a,a+'''
  initial_darken_opacity_ = darken_layer_ ? darken_layer_->opacity() : 0.0f;''')

def dim_h(s):
    s=once(s,'  scoped_refptr<cc::slim::SurfaceLayer> blur_layer_;','  scoped_refptr<cc::slim::SurfaceLayer> blur_layer_;\n  scoped_refptr<cc::slim::SolidColorLayer> darken_layer_;')
    return once(s,'  float initial_blur_opacity_ = 0.0f;', '  float initial_blur_opacity_ = 0.0f;\n  float initial_darken_opacity_ = 0.0f;')

def plan(root):
    root=Path(root)
    result={}
    for path in (CC,H):
        native=fixture(path);wanted=(dim_cc if path==CC else dim_h)(native)
        existing=(root/path).read_text()
        if existing in (native,wanted):
            result[root/path]=wanted
        elif path==CC:
            # Inner native restoration reapplies its exact reviewed diagnostics.
            # Accept only complete known postimages, never broad marker stripping.
            spec=importlib.util.spec_from_file_location(
                'native_blur_reviewed_probes',HERE.parent/'native-navigation/diagnostics.py')
            probes=importlib.util.module_from_spec(spec);spec.loader.exec_module(probes)
            diagnosed_native=probes.apply(path,native)
            diagnosed_wanted=probes.apply(path,wanted)
            if existing not in (diagnosed_native,diagnosed_wanted):
                raise ValueError('Expected exact restored Chromium156 native blur/probes: '+path)
            result[root/path]=diagnosed_wanted
        else:
            raise ValueError('Expected exact restored Chromium156 native blur source: '+path)
    # Do not replace all content_features: other Sandium features coexist here.
    # Require the pinned upstream blur feature block verbatim, and no old dim param.
    for path in (FC,FH):
        s=(root/path).read_text()
        if 'kAndroidNavigationAnimationDarken' in s:
            raise ValueError('Legacy blur dim parameter must be reversed before native156: '+path)
        native=fixture(path)
        if path==FC:
            start=native.index('BASE_FEATURE(kAndroidNavigationBlurTransitionAnimation')
            end=native.index('\n',native.index('3.0};',start))+1
            block=native[start:end]
        else:
            start=native.index('CONTENT_EXPORT BASE_DECLARE_FEATURE(kAndroidNavigationBlurTransitionAnimation)')
            end=native.index('kAndroidNavigationAnimationBlurSigma;',start)+len('kAndroidNavigationAnimationBlurSigma;')
            block=native[start:end]
        if block not in s:raise ValueError('Native156 blur feature defaults changed: '+path)
    return result

SETTINGS='brave/android/java/org/chromium/chrome/browser/settings/AppearancePreferences.java'
XML='brave/android/java/brave-res/xml/brave_appearance_preferences.xml'
KEY='sandium_page_transition_blur_enabled'
GRD='brave/browser/ui/android/strings/android_brave_strings.grd'
INPUTS.update({SETTINGS,XML,GRD})

def marked(s,name,body):
    begin='// SANDIUM_PAGE_TRANSITION_'+name+'_BEGIN'
    end='// SANDIUM_PAGE_TRANSITION_'+name+'_END'
    if s.count(begin)!=1 or s.count(end)!=1:raise ValueError('Settings marker drift: '+name)
    a=s.index(begin);b=s.index(end,a)+len(end)
    indent=s[s.rfind('\n',0,a)+1:a]
    if indent.strip():raise ValueError('Settings marker must start its own line')
    return s[:a]+begin+'\n'+body+'\n'+indent+end+s[b:]

def settings(s):
    s=marked(s,'BLUR_INIT','''        ChromeSwitchPreference pageTransitionBlur =
                (ChromeSwitchPreference) findPreference(PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL);
        if (pageTransitionBlur != null) {
            pageTransitionBlur.setChecked(isSandiumNativeBlurEnabled());
            pageTransitionBlur.setSummary(R.string.sandium_page_transition_blur_summary);
            pageTransitionBlur.setOnPreferenceChangeListener(this);
        }
        ChromeSwitchPreference pageTransitionDarken =
                (ChromeSwitchPreference) findPreference(PREF_SANDIUM_PAGE_TRANSITION_DARKEN);
        if (pageTransitionDarken != null) {
            pageTransitionDarken.setEnabled(isSandiumNativeBlurEnabled());
            pageTransitionDarken.setChecked(ContextUtils.getAppSharedPreferences()
                    .getBoolean(PREF_SANDIUM_PAGE_TRANSITION_DARKEN, false));
            pageTransitionDarken.setOnPreferenceChangeListener(this);
        }''')
    s=marked(s,'BLUR_HELPER','''    private static boolean isSandiumNativeBlurEnabled() {
        android.content.SharedPreferences prefs = ContextUtils.getAppSharedPreferences();
        if (prefs.contains("sandium_page_transition_blur_enabled")) {
            return prefs.getBoolean("sandium_page_transition_blur_enabled", true);
        }
        String legacy = prefs.getString("sandium_page_transition_blur_level", "on");
        return !"default".equals(legacy) && !"off".equals(legacy);
    }''')
    s=marked(s,'BLUR_CHANGE','''        if (PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL.equals(key)) {
            if (!(newValue instanceof Boolean)) return false;
            boolean saved = ContextUtils.getAppSharedPreferences().edit()
                    .putBoolean("sandium_page_transition_blur_enabled", (Boolean) newValue).commit();
            if (!saved) return false;
            Preference darken = findPreference(PREF_SANDIUM_PAGE_TRANSITION_DARKEN);
            if (darken != null) darken.setEnabled((Boolean) newValue);
            shouldRelaunch = true;
        }''')
    s=marked(s,'DARKEN_CHANGE','''        if (PREF_SANDIUM_PAGE_TRANSITION_DARKEN.equals(key)) {
            if (!(newValue instanceof Boolean) || !isSandiumNativeBlurEnabled()) return false;
            boolean saved = ContextUtils.getAppSharedPreferences().edit()
                    .putBoolean(PREF_SANDIUM_PAGE_TRANSITION_DARKEN, (Boolean) newValue).commit();
            if (!saved) return false;
            shouldRelaunch = true;
        }''')
    # Keep identifier for existing preference ordering/tests, replace only its key.
    s=once(s,'PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL = "sandium_page_transition_blur_level";',
              'PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL = "sandium_page_transition_blur_enabled";')
    return s

def xml(s):
    begin='<!-- SANDIUM_PAGE_TRANSITION_BLUR_BEGIN -->';end='<!-- SANDIUM_PAGE_TRANSITION_BLUR_END -->'
    if s.count(begin)!=1 or s.count(end)!=1:raise ValueError('Blur XML marker drift')
    a=s.index(begin);b=s.index(end,a)+len(end)
    block=s[a:b]
    # The legacy Full overlay nests the distinct Darken switch in this marker.
    # Replace only the blur node rather than removing the entire shared block.
    for token in (
        '<!-- SANDIUM_PAGE_TRANSITION_DARKEN_BEGIN -->',
        'android:key="sandium_page_transition_darken"',
        '@drawable/ic_sandium_page_transition_darken',
        '@string/sandium_page_transition_darken_title',
        '@string/sandium_page_transition_darken_summary',
        '<!-- SANDIUM_PAGE_TRANSITION_DARKEN_END -->',
    ):
        if block.count(token)!=1:raise ValueError('Darken XML anchor drift: '+token)
    legacy='''    <androidx.preference.ListPreference
        android:key="sandium_page_transition_blur_level"
        android:icon="@drawable/ic_sandium_page_transition_blur"
        android:persistent="false"
        android:defaultValue="default"
        android:title="@string/sandium_page_transition_blur_title"
        android:summary="@string/sandium_page_transition_blur_summary" />'''
    # The active native-navigation layer disables this exact legacy selector
    # before the outer overlay replaces it with the new live switch.
    disabled=legacy.replace(
        '        android:key="sandium_page_transition_blur_level"\n',
        '        android:key="sandium_page_transition_blur_level"\n        android:enabled="false"\n',1)
    present=[node for node in (legacy,disabled) if node in block]
    if len(present)!=1:raise ValueError('Native blur156 legacy selector anchor drift')
    return s[:a]+once(block,present[0],
        '''    <org.chromium.components.browser_ui.settings.ChromeSwitchPreference
        android:key="sandium_page_transition_blur_enabled"
        android:persistent="false"
        android:defaultValue="true"
        android:icon="@drawable/ic_sandium_page_transition_blur"
        android:title="@string/sandium_page_transition_blur_title" />''')+s[b:]

def strings(s):
    # These declarations were introduced by Sandium's legacy strength selector.
    for name,label in [('DEFAULT','Default'),('LOW','Low'),('MEDIUM','Medium'),('HIGH','High')]:
        block=('      <message name="IDS_SANDIUM_PAGE_TRANSITION_BLUR_'+name+'" desc="'+label+' page transition blur level.">\n'
               '        '+('Off' if name=='DEFAULT' else label)+'\n      </message>\n')
        s=once(s,block,'')
    return once(s,'Set how strongly the previous page blurs when opening another website',
                'Chromium native transition. Restart to apply')

native_plan=plan
def plan(root):
    root=Path(root);result=native_plan(root)
    result[root/SETTINGS]=settings((root/SETTINGS).read_text())
    result[root/XML]=xml((root/XML).read_text())
    result[root/GRD]=strings((root/GRD).read_text())
    return result
