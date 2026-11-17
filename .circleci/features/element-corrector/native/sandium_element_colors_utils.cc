// Copyright 2026 Sandium Authors. BSD-style license.
#include "brave/browser/android/cosmetic_filters/sandium_element_colors_utils.h"
#include "brave/browser/sandium/element_color_session.h"
#include "base/android/jni_android.h"
#include "base/android/jni_string.h"
#include "base/json/json_writer.h"
#include "base/strings/string_util.h"
#include "content/public/browser/browser_thread.h"
#include "brave/browser/brave_browser_process.h"
#include "brave/components/brave_shields/content/browser/ad_block_service.h"
#include "brave/components/brave_shields/content/browser/ad_block_custom_filters_provider.h"
#include <optional>
#include <string>
#include "chrome/browser/profiles/profile.h"
#include "brave/browser/sandium/element_color_rule_store.h"
#include "base/functional/bind.h"
#include "chrome/browser/android/tab_android.h"
#include "content/public/browser/web_contents.h"
#include "chrome/android/chrome_jni_headers/SandiumElementColorsUtils_jni.h"
namespace sandium {
namespace {
content::WebContents* Contents(JNIEnv* env,const base::android::JavaRef<jobject>& tab) {
  auto* native=TabAndroid::GetNativeTab(env,tab);return native ? native->web_contents() : nullptr;
}
ElementColorSession* Session(JNIEnv* env,const base::android::JavaRef<jobject>& tab,int64_t id) {
  auto* contents=Contents(env,tab);if(!contents)return nullptr;
  auto* session=ElementColorSession::FromWebContents(contents);
  return session && id>0 && session->request_id()==id ? session : nullptr;
}
void Result(base::WeakPtr<content::WebContents> contents,int64_t id,ElementColorSession::SaveResult result) {
  if(!contents)return;
  auto* tab=TabAndroid::FromWebContents(contents.get());if(!tab)return;
  Java_SandiumElementColorsUtils_onSaveResult(base::android::AttachCurrentThread(),tab->GetJavaObject(),id,static_cast<int>(result));
}
}
void NotifyElementColorSelection(content::WebContents* contents,int64_t id) {
  auto* tab=contents ? TabAndroid::FromWebContents(contents) : nullptr;if(!tab)return;
  Java_SandiumElementColorsUtils_onSelection(base::android::AttachCurrentThread(),tab->GetJavaObject(),id);
}
void NotifyElementColorSessionEnded(content::WebContents* contents,int64_t id) {
  auto* tab=contents ? TabAndroid::FromWebContents(contents) : nullptr;if(!tab)return;
  Java_SandiumElementColorsUtils_onSessionEnded(base::android::AttachCurrentThread(),tab->GetJavaObject(),id);
}
// Kept synchronous on the provider's UI sequence: no read/callback/write gap.
static std::optional<std::string> MergeCustomAdRules(const std::string& current,
                                             const std::string& incoming) {
  constexpr size_t limit = 8 * 1024 * 1024;
  if (current.size() > limit || incoming.size() > limit ||
      current.find('\0') != std::string::npos || incoming.find('\0') != std::string::npos ||
      !base::IsStringUTF8(current) || !base::IsStringUTF8(incoming)) return std::nullopt;
  if (incoming.empty() || current == incoming || current.ends_with("\n" + incoming))
    return current;
  const bool separator = !current.empty() && !current.ends_with("\n");
  if (incoming.size() > limit - current.size() ||
      (separator && incoming.size() == limit - current.size())) return std::nullopt;
  return current + (separator ? "\n" : "") + incoming;
}
static bool JNI_SandiumElementColorsUtils_AppendAdRules(
    JNIEnv* env,const base::android::JavaRef<jobject>& java_profile,
    const std::string& incoming) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  auto* profile=java_profile.is_null() ? nullptr : Profile::FromJavaObject(java_profile);
  if (!profile || profile->IsOffTheRecord() || !g_brave_browser_process) return false;
  auto* service=g_brave_browser_process->ad_block_service();
  auto* provider=service ? service->custom_filters_provider() : nullptr;
  if (!provider) return false;
  const std::string current=provider->GetCustomFilters();
  auto merged=MergeCustomAdRules(current,incoming);
  if (!merged) return false;
  return *merged == current || provider->UpdateCustomFilters(*merged);
}
static std::string JNI_SandiumElementColorsUtils_ExportRules(
    JNIEnv* env,const base::android::JavaRef<jobject>& java_profile) {
  if (java_profile.is_null()) return {};
  auto* profile=Profile::FromJavaObject(java_profile);
  if (!profile || profile->IsOffTheRecord()) return {};
  return ElementColorRuleStore::ForProfile(*profile).ExportRules();
}
static std::string JNI_SandiumElementColorsUtils_ImportRules(
    JNIEnv* env,const base::android::JavaRef<jobject>& java_profile,
    const std::string& json,bool apply) {
  auto* profile=java_profile.is_null() ? nullptr : Profile::FromJavaObject(java_profile);
  if (!profile || profile->IsOffTheRecord())
    return R"({"ok":false,"added":0,"conflicts":0,"duplicates":0,"error":"Available only in a regular profile."})";
  return base::WriteJson(ElementColorRuleStore::ForProfile(*profile).ImportRules(json,apply))
      .value_or(R"({"ok":false,"error":"Unable to encode import result."})");
}
static jboolean JNI_SandiumElementColorsUtils_Start(JNIEnv* env,const base::android::JavaRef<jobject>& tab,jlong id) {
  auto* contents=Contents(env,tab);return contents && ElementColorSession::GetOrCreate(contents).Begin(id);
}
static jboolean JNI_SandiumElementColorsUtils_Preview(JNIEnv* env,const base::android::JavaRef<jobject>& tab,jlong id,jint property,jint rgb) {
  auto* session=Session(env,tab,id);return session && rgb>=0 && session->Preview(property,static_cast<uint32_t>(rgb));
}
static void JNI_SandiumElementColorsUtils_Save(JNIEnv* env,const base::android::JavaRef<jobject>& tab,jlong id,jint property,jint rgb) {
  auto* contents=Contents(env,tab);auto* session=Session(env,tab,id);
  if(!contents)return;
  if(!session || rgb<0) {Result(contents->GetWeakPtr(),id,ElementColorSession::SaveResult::kRejected);return;}
  session->Save(property,static_cast<uint32_t>(rgb),base::BindOnce(&Result,contents->GetWeakPtr(),id));
}
static void JNI_SandiumElementColorsUtils_Cancel(JNIEnv* env,const base::android::JavaRef<jobject>& tab,jlong id) {
  if(auto* session=Session(env,tab,id))session->Cancel();
}
static void JNI_SandiumElementColorsUtils_ResetSite(JNIEnv* env,const base::android::JavaRef<jobject>& tab,jlong id) {
  if(auto* session=Session(env,tab,id))session->ResetSite();
}
}
DEFINE_JNI(SandiumElementColorsUtils)
