// Copyright 2026 Sandium Authors. BSD-style license.
#ifndef BRAVE_BROWSER_SANDIUM_ELEMENT_COLOR_RULE_STORE_H_
#define BRAVE_BROWSER_SANDIUM_ELEMENT_COLOR_RULE_STORE_H_
#include <map>
#include <string>
#include "base/values.h"
#include "base/memory/raw_ptr.h"
#include "url/origin.h"
class Profile;
class PrefRegistrySimple;
class PrefService;
namespace sandium {
// One instance per Profile-owned keyed service. Never share with original profile.
// Caller supplies browser-derived committed origin, never a renderer URL.
class ElementColorRuleStore {
 public:
  static void RegisterPrefs(PrefRegistrySimple*);
  static ElementColorRuleStore& ForProfile(Profile&);
  ElementColorRuleStore(PrefService*, bool off_the_record);
  ~ElementColorRuleStore();
  base::ListValue Read(const url::Origin&) const;
  bool Save(const url::Origin&, const base::DictValue&);
  bool Reset(const url::Origin&);
  void Clear();
  // Normal profiles only. Empty export denotes failure, not an empty ruleset.
  // Merge validates the entire input/projected store before a single pref write.
  // Existing target/property rules win conflicts; dry runs never mutate storage.
  std::string ExportRules() const;
  base::DictValue ImportRules(const std::string& json, bool apply);
  static bool ValidRule(const base::DictValue&);
 private:
  static bool EligibleOrigin(const url::Origin&);
  raw_ptr<PrefService> prefs_;
  const bool private_;
  std::map<std::string, base::ListValue> memory_;
};
}  // namespace sandium
#endif
