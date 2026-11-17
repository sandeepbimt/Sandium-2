"""Observed load outcomes, NOT a readiness/valid-active-generation claim."""
HEADER='components/brave_shields/content/browser/ad_block_service.h'
SOURCE='components/brave_shields/content/browser/ad_block_service.cc'
def once(s,old,new):
 if new in s:return s
 if s.count(old)!=1:raise ValueError('Ad load snapshot drift: '+old[:90])
 return s.replace(old,new,1)
def header(s):
 s=once(s,'#include <memory>','#include <array>\n#include <memory>')
 s=once(s,'  // Test accessors','''  // SANDIUM_AD_LOAD_OBSERVATIONS_V1: shared engine load completion outcomes.
  // Unknown=-1; failed updates do not imply the previous active engine is invalid.
  using SandiumDiagnosticLoadSnapshot = std::array<std::array<int64_t, 6>, 4>;
  SandiumDiagnosticLoadSnapshot GetSandiumDiagnosticLoadSnapshot() const;

  // Test accessors''')
 return once(s,'  raw_ptr<PrefService> local_state_;','''  std::array<int, 4> sandium_load_result_{{-1, -1, -1, -1}};
  std::array<int64_t, 4> sandium_load_sequence_{};
  int64_t sandium_next_load_sequence_ = 0;
  raw_ptr<PrefService> local_state_;''')
def source(s):
 s=once(s,'void AdBlockService::OnDATLoaded(bool is_default_engine, bool success) {\n  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);','''void AdBlockService::OnDATLoaded(bool is_default_engine, bool success) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  const size_t sandium_lane = is_default_engine ? 0 : 2;
  sandium_load_result_[sandium_lane] = success ? 1 : 0;
  sandium_load_sequence_[sandium_lane] = ++sandium_next_load_sequence_;''')
 s=once(s,'  auto [load_result, serialized_dat] = std::move(result);','''  auto [load_result, serialized_dat] = std::move(result);
  const size_t sandium_lane = is_default_engine ? 1 : 3;
  sandium_load_result_[sandium_lane] = static_cast<int>(load_result);
  sandium_load_sequence_[sandium_lane] = ++sandium_next_load_sequence_;''')
 return once(s,'void AdBlockService::OnDATLoaded(bool is_default_engine, bool success) {','''AdBlockService::SandiumDiagnosticLoadSnapshot
AdBlockService::GetSandiumDiagnosticLoadSnapshot() const {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  SandiumDiagnosticLoadSnapshot snapshot{};
  for (size_t i = 0; i < snapshot.size(); ++i) {
    snapshot[i] = {static_cast<int64_t>(i / 2), static_cast<int64_t>(i % 2),
                   sandium_load_result_[i], sandium_load_sequence_[i], -1, 1};
  }
  return snapshot;
}

void AdBlockService::OnDATLoaded(bool is_default_engine, bool success) {''')
