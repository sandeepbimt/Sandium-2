// SPDX-License-Identifier: MPL-2.0
namespace android {

static jint JNI_RawsProtectionCopy_GetAdFilteringPhase() {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  return static_cast<jint>(sandium::adblock_native::GetOfflineRulesPhase());
}

static bool JNI_RawsProtectionCopy_RequestFilterRefresh(Profile* profile) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  if (!sandium::adblock_native::OfflineRulesReady()) {
    return false;
  }
  auto* service = sandium::port1442::GetSubscriptions(profile);
  return service && service->RequestManualRefresh();
}

}  // namespace android
