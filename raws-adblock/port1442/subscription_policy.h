// SPDX-License-Identifier: MPL-2.0
// Policy from Sandium #1442's URL-subscription bootstrap and Brave 44a84b1.
#ifndef COMPONENTS_SANDIUM_ADBLOCK_SUBSCRIPTION_POLICY_H_
#define COMPONENTS_SANDIUM_ADBLOCK_SUBSCRIPTION_POLICY_H_
#include <cstdint>
namespace sandium::port1442 {
inline constexpr int kInitialSeconds = 60, kTickSeconds = 3600;
inline constexpr int kDefaultHours = 7 * 24, kMaxHours = 14 * 24;
struct Subscription {
  bool enabled = true, deleted = false;
  int expires_hours = kDefaultHours;
  int64_t attempt = 0, success = 0;
  bool Available() const { return enabled && !deleted; }
  bool Due(int64_t now, bool missing, bool manual) const {
    return Available() && (manual || missing || !success || attempt != success ||
        (now >= attempt && now - attempt >= int64_t(expires_hours) * 3600));
  }
};
}  // namespace sandium::port1442
#endif
