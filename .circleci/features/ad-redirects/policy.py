"""Install the Android ad-redirect profile preferences and their shared accessors."""
import argparse
from pathlib import Path

SHIELDS = "components/brave_shields/core/browser/brave_shields_utils"
PROFILE = "browser/brave_profile_prefs.cc"
BRIDGE = "browser/android/preferences/brave_pref_service_bridge.cc"
JAVA = "android/java/org/chromium/chrome/browser/preferences/BravePrefServiceBridge.java"

DECLARATIONS = '''#if BUILDFLAG(IS_ANDROID)
inline constexpr char kBlockAdRedirects[] = "sandium.block_ad_redirects";
inline constexpr char kAdRedirectSiteOverrides[] = "sandium.ad_redirect_site_overrides";

// Ordinals are shared with BravePrefServiceBridge's three site choices.
enum class AdRedirectSiteSetting { kDefault = 0, kBlock = 1, kAllow = 2 };
AdRedirectSiteSetting GetAdRedirectSiteSetting(const PrefService& prefs,
                                               const GURL& url);
void SetAdRedirectSiteSetting(PrefService& prefs,
                              const GURL& url,
                              AdRedirectSiteSetting setting);
bool ShouldBlockAdRedirect(const PrefService& prefs, const GURL& url);
#endif

'''

FUNCTIONS = '''#if BUILDFLAG(IS_ANDROID)
AdRedirectSiteSetting GetAdRedirectSiteSetting(const PrefService& prefs,
                                               const GURL& url) {
  if (!url.is_valid() || !url.SchemeIsHTTPOrHTTPS()) {
    return AdRedirectSiteSetting::kDefault;
  }
  const auto enabled = prefs.GetDict(kAdRedirectSiteOverrides)
                           .FindBool(url::Origin::Create(url).Serialize());
  if (!enabled.has_value()) {
    return AdRedirectSiteSetting::kDefault;
  }
  return *enabled ? AdRedirectSiteSetting::kBlock : AdRedirectSiteSetting::kAllow;
}

void SetAdRedirectSiteSetting(PrefService& prefs,
                              const GURL& url,
                              AdRedirectSiteSetting setting) {
  if (!url.is_valid() || !url.SchemeIsHTTPOrHTTPS() ||
      GetAdRedirectSiteSetting(prefs, url) == setting) {
    return;
  }
  const std::string origin = url::Origin::Create(url).Serialize();
  ScopedDictPrefUpdate update(prefs, kAdRedirectSiteOverrides);
  switch (setting) {
    case AdRedirectSiteSetting::kDefault:
      update->Remove(origin);
      break;
    case AdRedirectSiteSetting::kBlock:
    case AdRedirectSiteSetting::kAllow:
      update->Set(origin, setting == AdRedirectSiteSetting::kBlock);
      break;
  }
}

bool ShouldBlockAdRedirect(const PrefService& prefs, const GURL& url) {
  if (!url.is_valid() || !url.SchemeIsHTTPOrHTTPS()) {
    return false;
  }
  const auto setting = GetAdRedirectSiteSetting(prefs, url);
  return setting == AdRedirectSiteSetting::kDefault
             ? prefs.GetBoolean(kBlockAdRedirects)
             : setting == AdRedirectSiteSetting::kBlock;
}
#endif

'''

REGISTER = '''#if BUILDFLAG(IS_ANDROID)
  registry->RegisterBooleanPref(brave_shields::kBlockAdRedirects, true);
  registry->RegisterDictionaryPref(brave_shields::kAdRedirectSiteOverrides);
#endif
'''

JNI = '''jboolean JNI_BravePrefServiceBridge_IsAdRedirectBlockingEnabled(
    JNIEnv* env, const JavaRef<jobject>& j_profile) {
  return Profile::FromJavaObject(j_profile)->GetPrefs()->GetBoolean(
      brave_shields::kBlockAdRedirects);
}

void JNI_BravePrefServiceBridge_SetAdRedirectBlockingEnabled(
    JNIEnv* env, const JavaRef<jobject>& j_profile, jboolean enabled) {
  Profile::FromJavaObject(j_profile)->GetPrefs()->SetBoolean(
      brave_shields::kBlockAdRedirects, enabled);
}

jint JNI_BravePrefServiceBridge_GetAdRedirectSiteSetting(
    JNIEnv* env, const JavaRef<jobject>& j_profile, const JavaRef<jstring>& url) {
  return static_cast<jint>(brave_shields::GetAdRedirectSiteSetting(
      *Profile::FromJavaObject(j_profile)->GetPrefs(),
      GURL(base::android::ConvertJavaStringToUTF8(env, url))));
}

void JNI_BravePrefServiceBridge_SetAdRedirectSiteSetting(
    JNIEnv* env, const JavaRef<jobject>& j_profile, const JavaRef<jstring>& url,
    jint setting) {
  using Setting = brave_shields::AdRedirectSiteSetting;
  if (setting < static_cast<jint>(Setting::kDefault) ||
      setting > static_cast<jint>(Setting::kAllow)) {
    return;
  }
  brave_shields::SetAdRedirectSiteSetting(
      *Profile::FromJavaObject(j_profile)->GetPrefs(),
      GURL(base::android::ConvertJavaStringToUTF8(env, url)),
      static_cast<Setting>(setting));
}

'''

JAVA_API = '''    public static final int AD_REDIRECT_DEFAULT = 0;
    public static final int AD_REDIRECT_BLOCK = 1;
    public static final int AD_REDIRECT_ALLOW = 2;

    public static boolean isAdRedirectBlockingEnabled(Profile profile) {
        return BravePrefServiceBridgeJni.get().isAdRedirectBlockingEnabled(profile);
    }

    public static void setAdRedirectBlockingEnabled(Profile profile, boolean enabled) {
        BravePrefServiceBridgeJni.get().setAdRedirectBlockingEnabled(profile, enabled);
    }

    public static int getAdRedirectSiteSetting(Profile profile, GURL topLevelUrl) {
        return BravePrefServiceBridgeJni.get().getAdRedirectSiteSetting(
                profile, topLevelUrl.getValidSpecOrEmpty());
    }

    public static void setAdRedirectSiteSetting(Profile profile, GURL topLevelUrl, int setting) {
        BravePrefServiceBridgeJni.get().setAdRedirectSiteSetting(
                profile, topLevelUrl.getValidSpecOrEmpty(), setting);
    }

'''

NATIVES = '''        boolean isAdRedirectBlockingEnabled(Profile profile);
        void setAdRedirectBlockingEnabled(Profile profile, boolean enabled);
        int getAdRedirectSiteSetting(Profile profile, String topLevelUrl);
        void setAdRedirectSiteSetting(Profile profile, String topLevelUrl, int setting);

'''

def before(anchor, addition, marker=None):
    return anchor, addition + anchor, marker or addition.strip()


def after(anchor, addition, marker=None):
    return anchor, anchor + addition, marker or addition.strip()


# All five files already belong to existing production GN/JNI targets.
EDITS = {
    SHIELDS + ".h": [
        after('#include <string>\n', '\n#include "build/build_config.h"\n'),
        before("void SetBraveShieldsEnabled(", DECLARATIONS, "enum class AdRedirectSiteSetting "),
    ],
    SHIELDS + ".cc": [
        after('#include "components/prefs/pref_service.h"\n',
              '#include "components/prefs/scoped_user_pref_update.h"\n'),
        after('#include "url/gurl.h"\n', '#include "url/origin.h"\n'),
        before("void SetBraveShieldsEnabled(", FUNCTIONS, "AdRedirectSiteSetting GetAdRedirectSiteSetting("),
    ],
    PROFILE: [
        after('#include "brave/components/brave_shields/core/browser/brave_shields_p3a.h"\n',
              '#include "brave/components/brave_shields/core/browser/brave_shields_utils.h"\n'),
        after("void RegisterProfilePrefs(user_prefs::PrefRegistrySyncable* registry) {\n",
              REGISTER, "registry->RegisterDictionaryPref(brave_shields::kAdRedirectSiteOverrides);"),
    ],
    JAVA: [
        after("import org.chromium.chrome.browser.profiles.Profile;\n",
              "import org.chromium.url.GURL;\n"),
        before("    private static BravePrefServiceBridge sInstance;", JAVA_API, "int AD_REDIRECT_DEFAULT ="),
        after("    interface Natives {\n", NATIVES,
              "int getAdRedirectSiteSetting(Profile profile, String topLevelUrl);"),
    ],
    BRIDGE: [before("}  // namespace android\n", JNI, "jint JNI_BravePrefServiceBridge_GetAdRedirectSiteSetting(")],
}


def plan(core):
    result = {}
    for name, edits in EDITS.items():
        path = core / name
        original = path.read_text()
        updated = original
        for anchor, replacement, marker in edits:
            if updated.count(anchor) != 1:
                raise ValueError(f"{name}: unexpected count for {anchor.strip()}")
            if marker in updated:
                if updated.count(marker) != 1 or replacement not in updated:
                    raise ValueError(f"{name}: incomplete or duplicate ad-redirect policy")
            else:
                updated = updated.replace(anchor, replacement, 1)
        if original != updated:
            result[path] = updated
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("core", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    result = plan(args.core)
    if args.verify_only and result:
        parser.error("ad-redirect policy is missing: " + ", ".join(map(str, result)))
    for path, source in result.items():
        path.write_text(source)


if __name__ == "__main__":
    main()
