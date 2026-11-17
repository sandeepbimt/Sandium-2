// Native runtime state only. This is not a claim of filtering correctness.
static jint JNI_BraveShieldsContentSettings_GetSandiumBlockingEngineStatus(
    JNIEnv* env, const base::android::JavaRef<jobject>& j_profile) {
  auto* profile = Profile::FromJavaObject(j_profile);
  if (!profile) return 5;
  if (profile->IsOffTheRecord() ||
      !base::FeatureList::IsEnabled(features::kSandiumUboRuntime) ||
      !base::FeatureList::IsEnabled(sandium_ubo::kSandiumUboExclusiveRouting)) return 0;
  if (sandium_ubo::IsUboOwnerChosen(profile)) {
    if (sandium_ubo::MustBlockAdRequest(profile)) return 5;
    const auto state = extensions::api::GetSandiumUboRuntimeEligibility(profile);
    if (state.generation <= 0 || state.generation != state.acknowledged_generation ||
        !state.user_rules_applied || !state.policy_bridge_ready || !state.listeners_reported ||
        sandium_ubo::OwnerRestartRequired(profile)) return 2;
    return 1;
  }
  if (sandium_ubo::IsNativeFallbackComplete(profile)) return 3;
  if (sandium_ubo::IsRuntimeStartupAborted(profile)) return 5;
  return 4;
}
