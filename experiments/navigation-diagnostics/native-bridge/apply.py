#!/usr/bin/env python3
"""Held browser→existing Android JNI bridge; no event producers or CI wiring."""
from pathlib import Path
import argparse
PUBLIC_H='content/public/browser/content_browser_client.h'
PUBLIC_CC='content/public/browser/content_browser_client.cc'
CHROME_H='chrome/browser/chrome_content_browser_client.h'
CHROME_CC='chrome/browser/chrome_content_browser_client.cc'
THEME_H='chrome/browser/android/web_contents_theme_client.h'
THEME_CC='chrome/browser/android/web_contents_theme_client.cc'
JAVA='chrome/browser/ui/android/night_mode/java/src/org/chromium/chrome/browser/night_mode/WebContentsThemeClient.java'
BUILD='chrome/browser/ui/android/night_mode/BUILD.gn'
RECORDER='org/chromium/chrome/browser/sandium/diagnostics/SandiumNavigationDiagnostics.java'
REC='org.chromium.chrome.browser.sandium.diagnostics.SandiumNavigationDiagnostics'
MARK='SANDIUM_NAV_DIAGNOSTIC_BRIDGE_V1'
def once(s,old,new):
 if new in s:return s
 if s.count(old)!=1:raise ValueError('Diagnostic bridge anchor drift: '+old[:90])
 return s.replace(old,new,1)
def public_h(s):
 s=once(s,'#include <stddef.h>','#include <stddef.h>\n#include <cstdint>')
 return once(s,'  virtual bool OverrideWebPreferencesAfterNavigation(','''  // '''+MARK+''': UI-thread numeric diagnostics, disabled by default.
  virtual bool IsSandiumNavigationDiagnosticsEnabled(WebContents* web_contents);
  virtual int64_t GetSandiumNavigationDiagnosticsEpoch(WebContents* web_contents);
  virtual void RecordSandiumNavigationDiagnosticForEpoch(
      WebContents* web_contents, int64_t expected_epoch, int event_code,
      int64_t navigation_id, int64_t source_ticks_us, const std::vector<double>& values);
  virtual void RecordSandiumNavigationDiagnostic(
      WebContents* web_contents, int event_code, int64_t navigation_id,
      int64_t source_ticks_us, const std::vector<double>& values);

  virtual bool OverrideWebPreferencesAfterNavigation(''')
def public_cc(s):
 return once(s,'bool ContentBrowserClient::OverrideWebPreferencesAfterNavigation(','''bool ContentBrowserClient::IsSandiumNavigationDiagnosticsEnabled(WebContents*) {
  return false;
}

int64_t ContentBrowserClient::GetSandiumNavigationDiagnosticsEpoch(WebContents*) {
  return 0;
}

void ContentBrowserClient::RecordSandiumNavigationDiagnosticForEpoch(
    WebContents*, int64_t, int, int64_t, int64_t, const std::vector<double>&) {}

void ContentBrowserClient::RecordSandiumNavigationDiagnostic(
    WebContents*, int, int64_t, int64_t, const std::vector<double>&) {}

bool ContentBrowserClient::OverrideWebPreferencesAfterNavigation(''')
def chrome_h(s):
 return once(s,'  bool OverrideWebPreferencesAfterNavigation(','''  bool IsSandiumNavigationDiagnosticsEnabled(content::WebContents* web_contents) override;
  int64_t GetSandiumNavigationDiagnosticsEpoch(content::WebContents* web_contents) override;
  void RecordSandiumNavigationDiagnosticForEpoch(
      content::WebContents* web_contents, int64_t expected_epoch, int event_code,
      int64_t navigation_id, int64_t source_ticks_us,
      const std::vector<double>& values) override;
  void RecordSandiumNavigationDiagnostic(
      content::WebContents* web_contents, int event_code, int64_t navigation_id,
      int64_t source_ticks_us, const std::vector<double>& values) override;
  bool OverrideWebPreferencesAfterNavigation(''')
def chrome_cc(s):
 return once(s,'bool ChromeContentBrowserClient::OverrideWebPreferencesAfterNavigation(','''bool ChromeContentBrowserClient::IsSandiumNavigationDiagnosticsEnabled(
    WebContents* web_contents) {
#if BUILDFLAG(IS_ANDROID)
  // Reject non-UI callers before touching WebContents or its BrowserContext.
  if (!BrowserThread::CurrentlyOn(BrowserThread::UI) || !web_contents ||
      web_contents->GetBrowserContext()->IsOffTheRecord()) {
    return false;
  }
  return night_mode::WebContentsThemeClient::IsSandiumNavigationDiagnosticsEnabled(
      web_contents);
#else
  (void)web_contents;
  return false;
#endif
}

int64_t ChromeContentBrowserClient::GetSandiumNavigationDiagnosticsEpoch(
    WebContents* web_contents) {
#if BUILDFLAG(IS_ANDROID)
  if (!IsSandiumNavigationDiagnosticsEnabled(web_contents)) return 0;
  return night_mode::WebContentsThemeClient::GetSandiumNavigationDiagnosticsEpoch(
      web_contents);
#else
  (void)web_contents;
  return 0;
#endif
}

void ChromeContentBrowserClient::RecordSandiumNavigationDiagnosticForEpoch(
    WebContents* web_contents, int64_t expected_epoch, int event_code,
    int64_t navigation_id, int64_t source_ticks_us, const std::vector<double>& values) {
#if BUILDFLAG(IS_ANDROID)
  if (expected_epoch <= 0 || !IsSandiumNavigationDiagnosticsEnabled(web_contents) ||
      values.size() > 16 || navigation_id < 0 || source_ticks_us < 0) return;
  night_mode::WebContentsThemeClient::RecordSandiumNavigationDiagnosticForEpoch(
      web_contents, expected_epoch, event_code, navigation_id, source_ticks_us, values);
#else
  (void)web_contents; (void)expected_epoch; (void)event_code;
  (void)navigation_id; (void)source_ticks_us; (void)values;
#endif
}

void ChromeContentBrowserClient::RecordSandiumNavigationDiagnostic(
    WebContents* web_contents, int event_code, int64_t navigation_id,
    int64_t source_ticks_us, const std::vector<double>& values) {
#if BUILDFLAG(IS_ANDROID)
  if (!IsSandiumNavigationDiagnosticsEnabled(web_contents) || values.size() > 16 ||
      navigation_id < 0 || source_ticks_us < 0) {
    return;
  }
  night_mode::WebContentsThemeClient::RecordSandiumNavigationDiagnostic(
      web_contents, event_code, navigation_id, source_ticks_us, values);
#else
  (void)web_contents; (void)event_code; (void)navigation_id;
  (void)source_ticks_us; (void)values;
#endif
}

bool ChromeContentBrowserClient::OverrideWebPreferencesAfterNavigation(''')
def theme_h(s):
 s=once(s,'#include "content/public/browser/web_contents_user_data.h"','#include <cstdint>\n#include <vector>\n\n#include "content/public/browser/web_contents_user_data.h"')
 return once(s,'  bool IsNightModeEnabled();','''  // '''+MARK+''': existing JNI target, no dependency from content to chrome.
  static bool IsSandiumNavigationDiagnosticsEnabled(content::WebContents* web_contents);
  static int64_t GetSandiumNavigationDiagnosticsEpoch(content::WebContents* web_contents);
  static void RecordSandiumNavigationDiagnosticForEpoch(
      content::WebContents* web_contents, int64_t expected_epoch, int event_code,
      int64_t navigation_id, int64_t source_ticks_us, const std::vector<double>& values);
  static void RecordSandiumNavigationDiagnostic(
      content::WebContents* web_contents, int event_code, int64_t navigation_id,
      int64_t source_ticks_us, const std::vector<double>& values);
  bool IsNightModeEnabled();''')
def theme_cc(s):
 s=once(s,'#include "base/android/jni_android.h"','#include "base/android/jni_android.h"\n#include "base/android/jni_array.h"')
 return once(s,'namespace night_mode {','''namespace night_mode {

bool WebContentsThemeClient::IsSandiumNavigationDiagnosticsEnabled(
    content::WebContents* web_contents) {
  JNIEnv* env = base::android::AttachCurrentThread();
  return Java_WebContentsThemeClient_sandiumNavigationDiagnosticsEnabled(env, web_contents);
}

int64_t WebContentsThemeClient::GetSandiumNavigationDiagnosticsEpoch(
    content::WebContents* web_contents) {
  JNIEnv* env = base::android::AttachCurrentThread();
  return Java_WebContentsThemeClient_sandiumNavigationDiagnosticsEpoch(env, web_contents);
}

void WebContentsThemeClient::RecordSandiumNavigationDiagnosticForEpoch(
    content::WebContents* web_contents, int64_t expected_epoch, int event_code,
    int64_t navigation_id, int64_t source_ticks_us, const std::vector<double>& values) {
  JNIEnv* env = base::android::AttachCurrentThread();
  Java_WebContentsThemeClient_recordSandiumNavigationDiagnosticForEpoch(
      env, web_contents, expected_epoch, event_code, navigation_id, source_ticks_us,
      base::android::ToJavaDoubleArray(env, values));
}

void WebContentsThemeClient::RecordSandiumNavigationDiagnostic(
    content::WebContents* web_contents, int event_code, int64_t navigation_id,
    int64_t source_ticks_us, const std::vector<double>& values) {
  JNIEnv* env = base::android::AttachCurrentThread();
  Java_WebContentsThemeClient_recordSandiumNavigationDiagnostic(
      env, web_contents, event_code, navigation_id, source_ticks_us,
      base::android::ToJavaDoubleArray(env, values));
}

''')
def java(s):
 added='''
    // '''+MARK+''': no URL/title/DOM/string arguments accepted.
    @CalledByNative
    public static boolean sandiumNavigationDiagnosticsEnabled(
            @JniType("content::WebContents*") WebContents webContents) {
        if (webContents == null) return false;
        Profile profile = Profile.fromWebContents(webContents);
        if (profile == null || profile.isOffTheRecord()) return false;
        '''+REC+'''.initialize(new java.io.File(
                org.chromium.base.ContextUtils.getApplicationContext().getNoBackupFilesDir(),
                "sandium-diagnostics"));
        return '''+REC+'''.isRecording();
    }

    @CalledByNative
    public static long sandiumNavigationDiagnosticsEpoch(
            @JniType("content::WebContents*") WebContents webContents) {
        if (!sandiumNavigationDiagnosticsEnabled(webContents)) return 0;
        return '''+REC+'''.sessionEpoch();
    }

    @CalledByNative
    public static void recordSandiumNavigationDiagnosticForEpoch(
            @JniType("content::WebContents*") WebContents webContents,
            long expectedEpoch, int eventCode, long navigationId,
            long sourceTicksUs, double[] values) {
        if (webContents == null || expectedEpoch <= 0) return;
        Profile profile = Profile.fromWebContents(webContents);
        if (profile == null || profile.isOffTheRecord()) return;
        '''+REC+'''.recordNativeForEpoch(
                expectedEpoch, eventCode, navigationId, sourceTicksUs,
                profile.isOffTheRecord(), values);
    }

    @CalledByNative
    public static void recordSandiumNavigationDiagnostic(
            @JniType("content::WebContents*") WebContents webContents,
            int eventCode, long navigationId, long sourceTicksUs, double[] values) {
        if (webContents == null) return;
        Profile profile = Profile.fromWebContents(webContents);
        if (profile == null || profile.isOffTheRecord()) return;
        '''+REC+'''.recordNative(
                eventCode, navigationId, sourceTicksUs, profile.isOffTheRecord(), values);
    }
'''
 if added in s:return s
 if not s.endswith('}\n'):raise ValueError('Java class footer drift')
 return s[:-2]+added+'}\n'
def build(s):
 old='android_library("java") {\n  sources = [\n'
 return once(s,old,old+'    "java/src/'+RECORDER+'",\n')
TRANSFORMS={PUBLIC_H:public_h,PUBLIC_CC:public_cc,CHROME_H:chrome_h,CHROME_CC:chrome_cc,THEME_H:theme_h,THEME_CC:theme_cc,JAVA:java,BUILD:build}
def plan(src,recorder):
 outputs={src/p:fn((src/p).read_text()) for p,fn in TRANSFORMS.items()}
 text=recorder.read_text()
 if any(method not in text for method in ('recordNative(', 'recordNativeForEpoch(', 'sessionEpoch(')):raise ValueError('Recorder does not implement native transport contract')
 outputs[src/'chrome/browser/ui/android/night_mode/java/src'/RECORDER]=text
 return outputs
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--recorder',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
 output=plan(a.source,a.recorder)
 if a.apply:
  for path,text in output.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
 print('Numeric browser JNI bridge plan valid; no production activation or renderer transport')
