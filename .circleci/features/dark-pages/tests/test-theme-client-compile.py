#!/usr/bin/env python3
"""Compile exact transformed ThemeClient with API stubs, not an Android build."""
import hashlib,importlib.util,os,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[4]
spec=importlib.util.spec_from_file_location('dark',ROOT/'.circleci/scripts/apply-sandium-dark-pages.py');patch=importlib.util.module_from_spec(spec);spec.loader.exec_module(patch)
stubs={
'org/jni_zero/CalledByNative':'public @interface CalledByNative {}',
'org/jni_zero/JNINamespace':'public @interface JNINamespace {String value();}',
'org/chromium/build/annotations/NullMarked':'public @interface NullMarked {}',
'android/content/Context':'public class Context {}',
'org/chromium/url/GURL':'public class GURL {}',
'org/chromium/chrome/browser/flags/ChromeFeatureList':'public class ChromeFeatureList {public static final String FORCE_WEB_CONTENTS_DARK_MODE="f",DARKEN_WEBSITES_CHECKBOX_IN_THEMES_SETTING="d";public static boolean isEnabled(String s){return false;}}',
'org/chromium/chrome/browser/profiles/Profile':'public class Profile {public static Profile fromWebContents(org.chromium.content_public.browser.WebContents w){return null;}}',
'org/chromium/content_public/browser/WebContents':'public class WebContents {public org.chromium.ui.base.WindowAndroid getTopLevelNativeWindow(){return null;}public org.chromium.url.GURL getVisibleUrl(){return null;}}',
'org/chromium/ui/base/WindowAndroid':'public class WindowAndroid {public java.lang.ref.WeakReference<android.content.Context> getContext(){return null;}}',
'org/chromium/ui/util/ColorUtils':'public class ColorUtils {public static boolean inNightMode(android.content.Context c){return false;}}',
'org/chromium/chrome/browser/night_mode/WebContentsDarkModeController':'public class WebContentsDarkModeController {public static boolean isEnabledForUrl(org.chromium.chrome.browser.profiles.Profile p,org.chromium.url.GURL u){return false;}}',
'org/chromium/chrome/browser/night_mode/SandiumDarkPages':'public class SandiumDarkPages {public static int flags(org.chromium.content_public.browser.WebContents w,org.chromium.url.GURL u){return 0;}}',
}
java=str(pathlib.Path(os.environ['JAVA_HOME'])/'bin/java') if os.environ.get('JAVA_HOME') else 'java'
source=patch.theme((ROOT/'tests/fixtures/dark-pages'/patch.THEME).read_text())
old=source.replace('@JniType("GURL") GURL documentUrl','@JniType("GURL") org.chromium.url.GURL documentUrl')
assert patch.theme(old)==source
assert patch.theme(source)==source
with tempfile.TemporaryDirectory() as d:
 root=pathlib.Path(d);files=[]
 for path,body in stubs.items():
  f=root/(path+'.java');f.parent.mkdir(parents=True,exist_ok=True);f.write_text('package '+path.rsplit('/',1)[0].replace('/','.')+';\n'+body);files.append(str(f))
 annotation=root/'org/jni_zero/JniType.java'
 raw=(pathlib.Path(__file__).resolve().parent/'fixtures/JniType.java').read_bytes()
 assert hashlib.sha256(raw).hexdigest()=='d9a715da7c4d1da5e91f28fe2e26211e29b36e4d5c525d260bc177c06a03ba8e'
 annotation.write_bytes(raw);files.append(str(annotation))
 target=root/'org/chromium/chrome/browser/night_mode/WebContentsThemeClient.java';files.append(str(target))
 command=[java,'com.sun.tools.javac.Main','-d',str(root/'classes'),*files]
 target.write_text(old);negative=subprocess.run(command,capture_output=True,text=True)
 assert negative.returncode!=0 and 'scoping construct cannot be annotated' in negative.stderr,negative.stderr
 target.write_text(source);positive=subprocess.run(command,capture_output=True,text=True)
 assert positive.returncode==0,positive.stderr
print('Exact transformed ThemeClient compiles; old qualified TYPE_USE syntax rejected. APIs stubbed, not Android/JNI generation.')
