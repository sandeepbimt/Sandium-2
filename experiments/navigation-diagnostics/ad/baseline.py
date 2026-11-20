"""Explicit regular Settings Profile -> existing Brave JNI load snapshot."""
JAVA='android/java/org/chromium/chrome/browser/shields/FilterListServiceFactory.java'
CPP='browser/brave_shields/android/filter_list_service_factory_android.cc'
REC='org.chromium.chrome.browser.sandium.diagnostics.SandiumNavigationDiagnostics'
def once(s,old,new):
 if new in s:return s
 if s.count(old)!=1:raise ValueError('Ad baseline anchor drift: '+old[:90])
 return s.replace(old,new,1)
JAVA_METHOD='''    // SANDIUM_AD_START_BASELINE_V1: numeric shared load observations, not site readiness.
    public static boolean captureSandiumDiagnosticLoadSnapshot(
            @Nullable Profile profile, long expectedEpoch) {
        if (profile == null || profile.isOffTheRecord() || expectedEpoch <= 0
                || '''+REC+'''.sessionEpoch() != expectedEpoch) return false;
        double[] snapshot = FilterListServiceFactoryJni.get()
                .getSandiumDiagnosticLoadSnapshot(profile);
        if (snapshot == null || snapshot.length != 25) return false;
        for (double number : snapshot) if (!Double.isFinite(number)) return false;
        // Integer microseconds must survive primitive-double JNI without rounding.
        if (snapshot[0] < 0 || snapshot[0] > 9007199254740991.0
                || snapshot[0] != Math.rint(snapshot[0])) return false;
        if (profile.isOffTheRecord()
                || '''+REC+'''.sessionEpoch() != expectedEpoch) return false;
        long sourceTicksUs = (long) snapshot[0];
        for (int row = 0; row < 4; row++) {
            double[] values = java.util.Arrays.copyOfRange(snapshot, 1 + row * 6, 7 + row * 6);
            '''+REC+'''.recordNativeForEpoch(
                    expectedEpoch, 10, 0, sourceTicksUs, profile.isOffTheRecord(), values);
        }
        return true;
    }

'''
GATE_JAVA = '''    public static void setSandiumAdDiagnosticsRecording(boolean recording) {
        FilterListServiceFactoryJni.get().setSandiumAdDiagnosticsRecording(recording);
    }

'''
def java(s):
 s=once(s,'    @NativeMethods\n    interface Natives {','    @NativeMethods\n    interface Natives {\n        void setSandiumAdDiagnosticsRecording(boolean recording);')
 gate_anchor='    // SANDIUM_AD_START_BASELINE_V1:'
 s=once(s,'    @NativeMethods\n    interface Natives {',JAVA_METHOD+'    @NativeMethods\n    interface Natives {')
 s=once(s,gate_anchor,GATE_JAVA+gate_anchor)
 return once(s,'        long getInterfaceToFilterListService(Profile profile);','        double[] getSandiumDiagnosticLoadSnapshot(Profile profile);\n        long getInterfaceToFilterListService(Profile profile);')
CPP_METHOD='''static base::android::ScopedJavaLocalRef<jdoubleArray>
JNI_FilterListServiceFactory_GetSandiumDiagnosticLoadSnapshot(
    JNIEnv* env, const base::android::JavaRef<jobject>& profile_android) {
  std::vector<double> values;
  if (!content::BrowserThread::CurrentlyOn(content::BrowserThread::UI) ||
      profile_android.is_null()) return base::android::ToJavaDoubleArray(env, values);
  auto* profile = Profile::FromJavaObject(profile_android);
  if (!profile || profile->IsOffTheRecord() || !g_brave_browser_process) {
    return base::android::ToJavaDoubleArray(env, values);
  }
  auto* service = g_brave_browser_process->ad_block_service();
  if (!service) return base::android::ToJavaDoubleArray(env, values);
  const auto snapshot = service->GetSandiumDiagnosticLoadSnapshot();
  values.reserve(25);
  values.push_back(static_cast<double>(base::TimeTicks::Now().since_origin().InMicroseconds()));
  for (const auto& row : snapshot) {
    for (int64_t number : row) values.push_back(static_cast<double>(number));
  }
  return base::android::ToJavaDoubleArray(env, values);
}

'''
GATE_CPP = '''static void JNI_FilterListServiceFactory_SetSandiumAdDiagnosticsRecording(
    JNIEnv*, jboolean recording) {
  brave_shields::AdBlockService::SetSandiumAdDiagnosticsRecording(recording);
}

'''
def cpp(s):
 s=once(s,'#include "base/android/jni_android.h"','''#include <vector>
#include "base/android/jni_android.h"
#include "base/android/jni_array.h"
#include "base/time/time.h"
#include "brave/browser/brave_browser_process.h"
#include "brave/components/brave_shields/content/browser/ad_block_service.h"
#include "content/public/browser/browser_thread.h"''')
 s=once(s,'static jlong JNI_FilterListServiceFactory_GetInterfaceToFilterListService(',CPP_METHOD+'static jlong JNI_FilterListServiceFactory_GetInterfaceToFilterListService(')
 return once(s,CPP_METHOD, GATE_CPP+CPP_METHOD)
