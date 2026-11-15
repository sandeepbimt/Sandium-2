// Copyright 2026 Sandium Authors. BSD-style license.
#include "brave/browser/android/cosmetic_filters/sandium_element_colors_utils.h"
#include "brave/browser/sandium/element_color_session.h"
#include "base/android/jni_android.h"
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
