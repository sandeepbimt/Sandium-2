#ifndef BRAVE_COMPONENTS_SANDIUM_UBO_ROUTING_OWNER_STATE_H_
#define BRAVE_COMPONENTS_SANDIUM_UBO_ROUTING_OWNER_STATE_H_
#include <cstdint>
namespace sandium_ubo {
// Immutable after the first native boundary. No asynchronous native result can
// cross into a later uBO epoch because live switching is deliberately forbidden.
class OwnerState {
 public:
  bool PrepareUbo(uint64_t generation, bool prerequisites_verified) {
    if (sealed_ || !prerequisites_verified || generation == 0) return false;
    ubo_ = true;
    generation_ = generation;
    return true;
  }
  bool AcknowledgeSettings(uint64_t generation) {
    if (!ubo_ || generation == 0) return false;
    generation_ = generation;
    restart_required_ = false;
    return true;
  }
  bool SealAndUseNative() {
    sealed_ = true;
    return !ubo_;
  }
  void Invalidate(uint64_t generation) {
    if (!ubo_ || generation == generation_) return;
    if (!sealed_) { ubo_ = false; generation_ = 0; }
    // A live settings change does not change engine ownership or require restart.
  }
  uint64_t generation() const { return generation_; }
  bool ubo_selected() const { return ubo_; }
  bool restart_required() const { return restart_required_; }
 private:
  bool sealed_ = false;
  bool ubo_ = false;
  bool restart_required_ = false;
  uint64_t generation_ = 0;
};
}  // namespace sandium_ubo
#endif
