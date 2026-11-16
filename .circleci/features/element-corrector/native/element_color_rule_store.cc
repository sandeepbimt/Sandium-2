// Copyright 2026 Sandium Authors. BSD-style license.
#include "brave/browser/sandium/element_color_rule_store.h"
#include "components/prefs/pref_registry_simple.h"
#include "chrome/browser/profiles/profile.h"
#include "base/supports_user_data.h"
#include <memory>
#include "components/prefs/pref_service.h"
#include "components/prefs/scoped_user_pref_update.h"

namespace sandium {
namespace {
constexpr char kStoreKey[] = "sandium.element_colors.profile_store";
class ProfileStore final : public base::SupportsUserData::Data {
 public:
  explicit ProfileStore(Profile& profile) : store(profile.GetPrefs(), profile.IsOffTheRecord()) {}
  ElementColorRuleStore store;
};
constexpr char kPref[] = "sandium.element_colors.rules_v1";
constexpr size_t kSites = 128;
constexpr size_t kRules = 32;
bool BoundedText(const std::string* text, size_t limit, bool allow_empty) {
  if (!text || text->size() > limit || (!allow_empty && text->empty())) return false;
  for (unsigned char ch : *text) if (ch < 32 || ch == 127) return false;
  return true;
}
bool Tag(const std::string* text) {
  if (!BoundedText(text, 64, false)) return false;
  for (unsigned char ch : *text)
    if (!((ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9') || ch == '-')) return false;
  return true;
}
bool SameTarget(const base::DictValue& a, const base::DictValue& b) {
  return a.FindString("id") && b.FindString("id") &&
      *a.FindString("id") == *b.FindString("id") && a.FindInt("property") == b.FindInt("property");
}
}  // namespace
ElementColorRuleStore& ElementColorRuleStore::ForProfile(Profile& profile) {
  auto* holder = static_cast<ProfileStore*>(profile.GetUserData(kStoreKey));
  if (!holder) {
    auto owned = std::make_unique<ProfileStore>(profile);
    holder = owned.get();
    profile.SetUserData(kStoreKey,std::move(owned));
  }
  return holder->store;
}
void ElementColorRuleStore::RegisterPrefs(PrefRegistrySimple* registry) {
  registry->RegisterDictionaryPref(kPref);  // Non-syncable by construction.
}
ElementColorRuleStore::ElementColorRuleStore(PrefService* prefs, bool off_the_record)
    : prefs_(off_the_record ? nullptr : prefs), private_(off_the_record) {}
ElementColorRuleStore::~ElementColorRuleStore() = default;
bool ElementColorRuleStore::EligibleOrigin(const url::Origin& origin) {
  return !origin.opaque() && origin.GetURL().SchemeIsHTTPOrHTTPS();
}
bool ElementColorRuleStore::ValidRule(const base::DictValue& rule) {
  // No CSS/JS, URLs, text content, or arbitrary nested data is accepted.
  if (rule.size() != 6 || !Tag(rule.FindString("tag")) ||
      !BoundedText(rule.FindString("id"), 128, false) ||
      !BoundedText(rule.FindString("role"), 64, true)) return false;
  auto property = rule.FindInt("property"), rgb = rule.FindInt("rgb");
  if (!property || (*property != 0 && *property != 1 && *property != 2) || !rgb || *rgb < 0 || *rgb > 0xffffff) return false;
  if (*property == 2 && *rule.FindString("tag") != "img") return false;
  const auto* ancestors = rule.FindList("ancestors");
  if (!ancestors || ancestors->size() > 24) return false;
  for (const auto& item : *ancestors) {
    const auto* entry = item.GetIfDict();
    if (!entry || entry->size() != 2 || !Tag(entry->FindString("tag")) ||
        !BoundedText(entry->FindString("id"),128,true)) return false;
  }
  return true;
}
base::ListValue ElementColorRuleStore::Read(const url::Origin& origin) const {
  base::ListValue clean;
  if (!EligibleOrigin(origin)) return clean;
  const base::ListValue* list = nullptr;
  if (private_) {
    auto found = memory_.find(origin.Serialize());
    if (found != memory_.end()) list = &found->second;
  } else if (prefs_) {
    list = prefs_->GetDict(kPref).FindList(origin.Serialize());
  }
  if (!list || list->size() > kRules) return clean;
  for (const auto& item : *list) {
    const auto* rule = item.GetIfDict();
    if (rule && ValidRule(*rule)) clean.Append(rule->Clone());
  }
  return clean;
}
bool ElementColorRuleStore::Save(const url::Origin& origin, const base::DictValue& rule) {
  if (!EligibleOrigin(origin) || !ValidRule(rule) || (!private_ && !prefs_)) return false;
  const std::string key = origin.Serialize();
  base::ListValue result;
  for (const auto& item : Read(origin))
    if (!SameTarget(item.GetDict(),rule)) result.Append(item.Clone());
  if (result.size() >= kRules) return false;
  result.Append(rule.Clone());
  if (private_) {
    if (!memory_.contains(key) && memory_.size() >= kSites) return false;
    memory_.insert_or_assign(key,std::move(result));
  } else {
    if (!prefs_->GetDict(kPref).contains(key) && prefs_->GetDict(kPref).size() >= kSites) return false;
    ScopedDictPrefUpdate update(prefs_,kPref);
    update->Set(key,std::move(result));
  }
  return true;
}
bool ElementColorRuleStore::Reset(const url::Origin& origin) {
  if (!EligibleOrigin(origin) || (!private_ && !prefs_)) return false;
  if (private_) memory_.erase(origin.Serialize());
  else { ScopedDictPrefUpdate update(prefs_,kPref); update->Remove(origin.Serialize()); }
  return true;
}
void ElementColorRuleStore::Clear() {
  if (private_) memory_.clear();
  else if (prefs_) prefs_->ClearPref(kPref);
}
}  // namespace sandium
