#!/usr/bin/env python3
"""Pinned general resource bootstrap/reload hardening; no domain exceptions.

Apply AFTER Sandium engine-race and warmup transformations. Never restores files.
"""
from pathlib import Path
import subprocess
import re
import sys

PIN = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
BASE = "components/brave_shields/"

def replace(source, old, new, label):
    if new in source:
        return source
    if source.count(old) != 1:
        raise RuntimeError(f"{label}: expected exactly one pinned anchor")
    return source.replace(old, new, 1)


def default_header(s):
    s = replace(s, '#include "base/functional/callback.h"',
                '#include <cstdint>\n#include <string>\n\n#include "base/functional/callback.h"', 'default includes')
    s = replace(s, '  friend class ::AdBlockServiceTest;', '  friend class ::AdBlockServiceTest;\n  friend class AdBlockDefaultResourceProviderTest;', 'resource test fixture')
    return replace(s, '  base::FilePath component_path_;',
        '  // Sandium: publish only the newest validated component read. A failed read\n  // cannot clear resources already serving the active engines.\n  void OnResourcesRead(uint64_t generation,\n                       const base::FilePath& path,\n                       const std::string& resources_json);\n  uint64_t resource_generation_ = 0;\n  AdblockResourceStorageBox validated_storage_;\n  base::FilePath component_path_;', 'default members')


def default_cc(s):
    s = replace(s, '#include "base/files/file_path.h"',
                '#include "base/files/file_path.h"\n#include "base/logging.h"', 'logging include')
    s = replace(s, 'constexpr char kAdBlockResourcesFilename[] = "resources.json";',
        'constexpr char kAdBlockResourcesFilename[] = "resources.json";\n\n// Sandium\'s own minimal, unprivileged bootstrap resource. This is not an\n// arbitrary-redirect fallback: only rules explicitly naming noop.js/noopjs\n// resolve to it. Unknown resources retain upstream blocking semantics.\n// Full scriptlet functionality still requires the signed component bundle.\nconstexpr char kSandiumBootstrapResources[] = R"json([{"name":"noop.js","aliases":["noopjs"],"kind":{"mime":"application/javascript"},"content":"LyogU2FuZGl1bSBuby1vcCBzY3JpcHQuICov"}])json";\n// Insert the canonical resource alone into a component to avoid colliding\n// with an independently supplied noopjs alias.\nconstexpr char kSandiumCanonicalNoop[] = R"json([{"name":"noop.js","kind":{"mime":"application/javascript"},"content":"LyogU2FuZGl1bSBuby1vcCBzY3JpcHQuICov"}])json";', 'bootstrap resource')
    s = replace(s, '    component_updater::ComponentUpdateService* cus) {',
                '    component_updater::ComponentUpdateService* cus)\n    : validated_storage_(adblock::new_resource_storage(\n          std::string(kSandiumBootstrapResources))) {', 'initialize bootstrap')
    start=s.index('void AdBlockDefaultResourceProvider::OnComponentReady(')
    end=s.index('\n}  // namespace brave_shields',start)
    new='void AdBlockDefaultResourceProvider::OnComponentReady(\n    const base::FilePath& path) {\n  if (path.empty()) {\n    return;\n  }\n  const uint64_t generation = ++resource_generation_;\n  base::ThreadPool::PostTaskAndReplyWithResult(\n      FROM_HERE, {base::MayBlock()},\n      base::BindOnce(&brave_component_updater::GetDATFileAsString,\n                     path.AppendASCII(kAdBlockResourcesFilename)),\n      base::BindOnce(&AdBlockDefaultResourceProvider::OnResourcesRead,\n                     weak_factory_.GetWeakPtr(), generation, path));\n}\n\nvoid AdBlockDefaultResourceProvider::OnResourcesRead(\n    uint64_t generation,\n    const base::FilePath& path,\n    const std::string& resources_json) {\n  if (generation != resource_generation_) {\n    return;\n  }\n  // Validate with the same Rust parser/resource backend used by the engines.\n  // No unparsable/empty/unusable update may replace a known-good resource set.\n  if (!adblock::resource_storage_json_is_valid(resources_json)) {\n    LOG(WARNING) << "SANDIUM_ADBLOCK_RESOURCES invalid_update_retained_previous";\n    return;\n  }\n  auto storage = adblock::new_resource_storage(resources_json);\n  // Signed component content takes precedence. Supply the generic bootstrap\n  // only when the component genuinely omits this standard redirect resource.\n  const std::string noop_name = "noop.js";\n  if (!adblock::has_resource_for_testing(*storage, noop_name)) {\n    storage = adblock::extend_resource_storage(\n        *storage, kSandiumCanonicalNoop);\n  }\n  validated_storage_ = std::move(storage);\n  component_path_ = path;\n  NotifyResourcesLoaded(adblock::clone_resource_storage(*validated_storage_));\n}\n\nvoid AdBlockDefaultResourceProvider::LoadResources(\n    base::OnceCallback<void(AdblockResourceStorageBox)> cb) {\n  // Clone the Arc-backed immutable snapshot, not the full JSON bundle.\n  // Synchronous delivery cannot trail a newer resource notification.\n  std::move(cb).Run(adblock::clone_resource_storage(*validated_storage_));\n}\n'
    if 'SANDIUM_ADBLOCK_RESOURCES invalid_update_retained_previous' in s:
        if s[start:end] != new:
            raise RuntimeError('default implementation marker mismatch')
        return s
    return s[:start]+new+s[end:]


def rust_bridge(s):
    return replace(s, '        fn new_empty_resource_storage() -> Box<BraveCoreResourceStorage>;',
        '        fn resource_storage_json_is_valid(resources_json: &CxxString) -> bool;\n        fn new_empty_resource_storage() -> Box<BraveCoreResourceStorage>;', 'validation FFI')


def rust_storage(s):
    old='/// Creates a new empty ResourceStorage.'
    new="/// Sandium checks bundle parse/loadability before replacing last-known-good data.\n/// Uses the engine's parser and insertion checks. Individual resource errors\n/// retain upstream semantics; a compatible partial bundle must not be rejected\n/// merely because aliases overlap or an optional dependency is unavailable.\npub fn resource_storage_json_is_valid(resources_json: &CxxString) -> bool {\n    let Ok(json) = resources_json.to_str() else { return false; };\n    let Ok(resources) = serde_json::from_str::<Vec<Resource>>(json) else {\n        return false;\n    };\n    if resources.is_empty() {\n        return false;\n    }\n    let mut storage = InMemoryResourceStorage::default();\n    for resource in resources {\n        if storage.add_resource(resource).is_ok() {\n            return true;\n        }\n    }\n    false\n}\n\n/// Creates a new empty ResourceStorage."
    return replace(s, old, new, 'Rust validation')


def service_header(s):
    return replace(s, '    void OnDATFileRead(DATFileDataBuffer dat);',
        '    void OnDATFileRead(DATFileDataBuffer dat);\n    void OnDATResourcesLoaded(uint64_t generation,\n                              DATFileDataBuffer dat,\n                              AdblockResourceStorageBox storage);', 'DAT resources callback')


def service_cc(s):
    start=s.index('void AdBlockService::SourceProviderObserver::OnDATFileRead(')
    end=s.index('void AdBlockService::SourceProviderObserver::OnFilterSetCreated(',start)
    new='void AdBlockService::SourceProviderObserver::OnDATFileRead(\n    DATFileDataBuffer dat) {\n  // A provider rebuild supersedes the startup cache, including when the DAT\n  // disk read itself finishes after that rebuild began.\n  if (filter_set_generation_ != 0) {\n    return;\n  }\n  // Sandium: cached rules and resources enter the engine together. Publishing\n  // redirects against empty resources turns safe replacements into failures.\n  resource_provider_->AddObserver(this);\n  resource_provider_->LoadResources(base::BindOnce(\n      &SourceProviderObserver::OnDATResourcesLoaded, weak_factory_.GetWeakPtr(),\n      filter_set_generation_, std::move(dat)));\n}\n\nvoid AdBlockService::SourceProviderObserver::OnDATResourcesLoaded(\n    uint64_t generation,\n    DATFileDataBuffer dat,\n    AdblockResourceStorageBox storage) {\n  if (generation != filter_set_generation_) {\n    return;\n  }\n  on_resources_loaded_.Run(engine_is_default_, std::move(dat), nullptr,\n                           std::move(storage));\n}\n\n'
    if 'void AdBlockService::SourceProviderObserver::OnDATResourcesLoaded(' in s:
        if s[start:end] != new:
            raise RuntimeError('DAT resource patch marker mismatch')
        return s
    # Require the exact known DAT behavior from the earlier engine-race patch.
    # Ignore comments/formatting only; never overwrite another native edit.
    expected = """void AdBlockService::SourceProviderObserver::OnDATFileRead(
    DATFileDataBuffer dat) {
  on_resources_loaded_.Run(engine_is_default_, std::move(dat), nullptr,
                           adblock::new_empty_resource_storage());
  LoadResources(nullptr, filter_set_generation_);
}
"""
    normalize = lambda value: re.sub(r"\s+", "", re.sub(r"//[^\n]*", "", value))
    if normalize(s[start:end]) != normalize(expected):
        raise RuntimeError('unexpected DAT body: apply engine-race first; review conflicting edits')
    return s[:start]+new+s[end:]


def custom_header(s):
    s = replace(s, '#include <memory>', '#include <cstdint>\n#include <memory>', 'custom integer include')
    s = replace(s, '  void OnDefaultResourcesLoaded(\n      base::OnceCallback<void(AdblockResourceStorageBox)> on_load,',
                '  void OnDefaultResourcesLoaded(\n      uint64_t generation,\n      base::OnceCallback<void(AdblockResourceStorageBox)> on_load,', 'default merge generation')
    s = replace(s, '  void OnCustomResourcesLoaded(\n      base::OnceCallback<void(AdblockResourceStorageBox)> on_load,',
                '  void OnCustomResourcesLoaded(\n      uint64_t generation,\n      base::OnceCallback<void(AdblockResourceStorageBox)> on_load,', 'custom merge generation')
    return replace(s, '  std::optional<AdblockResourceStorageBox> cached_storage_ = std::nullopt;',
                   '  std::optional<AdblockResourceStorageBox> cached_storage_ = std::nullopt;\n  uint64_t resource_generation_ = 0;  // Sandium resource merge generation.', 'custom generation member')


def custom_cc(s):
    # A cached snapshot is delivered immediately on this provider's sequence;
    # posting the old snapshot allowed it to arrive after a newer notification.
    old='''    base::SequencedTaskRunner::GetCurrentDefault()->PostTask(
        FROM_HERE,
        base::BindOnce(std::move(on_load), adblock::clone_resource_storage(
                                               *cached_storage_.value())));'''
    new='''    // Sandium: do not post an old snapshot behind a newer resource update.
    std::move(on_load).Run(
        adblock::clone_resource_storage(*cached_storage_.value()));'''
    s=replace(s,old,new,'synchronous cached resource snapshot')
    s=replace(s, '''      base::BindOnce(&AdBlockCustomResourceProvider::OnDefaultResourcesLoaded,
                     weak_ptr_factory_.GetWeakPtr(), std::move(on_load)));''',
        '''      base::BindOnce(&AdBlockCustomResourceProvider::OnDefaultResourcesLoaded,
                     weak_ptr_factory_.GetWeakPtr(), resource_generation_,
                     std::move(on_load)));''','stamp default resource load')
    s=replace(s, '''  cached_storage_.reset();
  OnDefaultResourcesLoaded(
      base::BindOnce(&AdBlockCustomResourceProvider::NotifyResourcesLoaded,''',
        '''  ++resource_generation_;
  cached_storage_.reset();
  OnDefaultResourcesLoaded(
      resource_generation_,
      base::BindOnce(&AdBlockCustomResourceProvider::NotifyResourcesLoaded,''','advance component resource generation')
    s=replace(s, '''void AdBlockCustomResourceProvider::OnDefaultResourcesLoaded(
    base::OnceCallback<void(AdblockResourceStorageBox)> on_load,
    AdblockResourceStorageBox storage) {
  GetCustomResources(base::BindOnce(''',
        '''void AdBlockCustomResourceProvider::OnDefaultResourcesLoaded(
    uint64_t generation,
    base::OnceCallback<void(AdblockResourceStorageBox)> on_load,
    AdblockResourceStorageBox storage) {
  if (generation != resource_generation_) {
    LoadResources(std::move(on_load));
    return;
  }
  GetCustomResources(base::BindOnce(''','reject outdated default snapshot')
    s=replace(s, '''      &AdBlockCustomResourceProvider::OnCustomResourcesLoaded,
      weak_ptr_factory_.GetWeakPtr(), std::move(on_load), std::move(storage)));''',
        '''      &AdBlockCustomResourceProvider::OnCustomResourcesLoaded,
      weak_ptr_factory_.GetWeakPtr(), generation, std::move(on_load),
      std::move(storage)));''','stamp custom merge')
    s=replace(s, '''void AdBlockCustomResourceProvider::OnCustomResourcesLoaded(
    base::OnceCallback<void(AdblockResourceStorageBox)> on_load,
    AdblockResourceStorageBox default_storage,
    base::Value custom_resources) {
  CHECK(custom_resources.is_list());''',
        '''void AdBlockCustomResourceProvider::OnCustomResourcesLoaded(
    uint64_t generation,
    base::OnceCallback<void(AdblockResourceStorageBox)> on_load,
    AdblockResourceStorageBox default_storage,
    base::Value custom_resources) {
  if (generation != resource_generation_) {
    // Fulfil the caller with the newest generation, never a stale merged cache.
    LoadResources(std::move(on_load));
    return;
  }
  CHECK(custom_resources.is_list());''','reject outdated custom merge')
    s=replace(s, '''void AdBlockCustomResourceProvider::ReloadResourcesAndNotify() {
  cached_storage_.reset();''',
        '''void AdBlockCustomResourceProvider::ReloadResourcesAndNotify() {
  ++resource_generation_;
  cached_storage_.reset();''','advance user resource generation')
    s=replace(s, '''void AdBlockCustomResourceProvider::OverrideResourcesForTesting(
    AdblockResourceStorageBox storage) {
  cached_storage_''',
        '''void AdBlockCustomResourceProvider::OverrideResourcesForTesting(
    AdblockResourceStorageBox storage) {
  ++resource_generation_;
  cached_storage_''','testing resource generation')
    return s


def resource_tests(s):
    s = replace(s, '#include "base/base64.h"', '#include "brave/components/brave_shields/core/browser/ad_block_default_resource_provider.h"\n#include "base/base64.h"', 'default resource test include')
    anchor = 'namespace brave_shields {\n'
    return replace(s, anchor, anchor + '\n' + RESOURCE_TESTS, 'resource regression tests')

RESOURCE_TESTS = '// Sandium resource regressions. These are engine/provider tests, not Android\n// proxy-response or renderer tests; CI compilation does not execute them.\nclass AdBlockDefaultResourceProviderTest : public testing::Test {\n protected:\n  void Read(AdBlockDefaultResourceProvider& provider,\n            uint64_t generation,\n            const std::string& json) {\n    provider.OnResourcesRead(generation, base::FilePath(FILE_PATH_LITERAL("test")),\n                             json);\n  }\n  void Begin(AdBlockDefaultResourceProvider& provider, uint64_t generation) {\n    provider.resource_generation_ = generation;\n  }\n  bool Has(AdBlockDefaultResourceProvider& provider, const std::string& name) {\n    base::test::TestFuture<AdblockResourceStorageBox> result;\n    provider.LoadResources(result.GetCallback());\n    return adblock::has_resource_for_testing(*result.Get(), name);\n  }\n};\n\nTEST_F(AdBlockDefaultResourceProviderTest, BootstrapNoopBeforeComponentReady) {\n  AdBlockDefaultResourceProvider provider(nullptr);\n  EXPECT_TRUE(Has(provider, "noop.js"));\n  EXPECT_TRUE(Has(provider, "noopjs"));\n  EXPECT_FALSE(Has(provider, "arbitrary-unknown.js"));\n}\n\nTEST_F(AdBlockDefaultResourceProviderTest, InvalidUpdatePreservesPreviousBundle) {\n  AdBlockDefaultResourceProvider provider(nullptr);\n  Begin(provider, 1);\n  Read(provider, 1, R"json([{"name":"known-good.js","kind":{"mime":"application/javascript"},"content":"Lyogb2sgKi8="}])json");\n  EXPECT_TRUE(Has(provider, "known-good.js"));\n  for (const std::string& invalid : {\n           std::string(""), std::string("[]"), std::string("not-json"),\n           std::string(R"json([{"name":"bad.js","kind":{"mime":"application/javascript"},"content":"%invalid%"}])json")}) {\n    Read(provider, 1, invalid);\n    EXPECT_TRUE(Has(provider, "known-good.js"));\n    EXPECT_TRUE(Has(provider, "noop.js"));\n  }\n}\n\nTEST_F(AdBlockDefaultResourceProviderTest, OlderReadCannotReplaceNewerResources) {\n  AdBlockDefaultResourceProvider provider(nullptr);\n  Begin(provider, 2);\n  Read(provider, 2, R"json([{"name":"new.js","kind":{"mime":"application/javascript"},"content":"Lyogb2sgKi8="}])json");\n  Read(provider, 1, R"json([{"name":"old.js","kind":{"mime":"application/javascript"},"content":"Lyogb2sgKi8="}])json");\n  EXPECT_TRUE(Has(provider, "new.js"));\n  EXPECT_FALSE(Has(provider, "old.js"));\n}\n\nTEST_F(AdBlockDefaultResourceProviderTest, PartialBundleKeepsUpstreamSkipSemantics) {\n  AdBlockDefaultResourceProvider provider(nullptr);\n  Begin(provider, 1);\n  // The upstream loader skips individually unusable entries and permits\n  // optional dependencies. Do not reject all valid resources in that case.\n  Read(provider, 1, R"json([{"name":"broken.js","kind":{"mime":"application/javascript"},"content":"%invalid%"},{"name":"working.js","kind":{"mime":"application/javascript"},"content":"Lyogb2sgKi8="},{"name":"optional.js","kind":{"mime":"application/javascript"},"content":"Lyogb2sgKi8=","dependencies":["absent.js"]}])json");\n  EXPECT_TRUE(Has(provider, "working.js"));\n  EXPECT_TRUE(Has(provider, "optional.js"));\n  EXPECT_FALSE(Has(provider, "broken.js"));\n}\n\nTEST_F(AdBlockDefaultResourceProviderTest, ExistingAliasCannotBlockCanonicalBootstrap) {\n  AdBlockDefaultResourceProvider provider(nullptr);\n  Begin(provider, 1);\n  Read(provider, 1, R"json([{"name":"noopjs","kind":{"mime":"application/javascript"},"content":"Lyogb2sgKi8="}])json");\n  EXPECT_TRUE(Has(provider, "noopjs"));\n  EXPECT_TRUE(Has(provider, "noop.js"));\n}\n\n'

TRANSFORMS = {
    BASE+'core/browser/ad_block_custom_resource_provider_unittest.cc': resource_tests,
    BASE+'core/browser/ad_block_custom_resource_provider.h': custom_header,
    BASE+'core/browser/ad_block_custom_resource_provider.cc': custom_cc,
    BASE+'core/browser/ad_block_default_resource_provider.h': default_header,
    BASE+'core/browser/ad_block_default_resource_provider.cc': default_cc,
    BASE+'core/common/adblock/rs/src/lib.rs': rust_bridge,
    BASE+'core/common/adblock/rs/src/resource_storage.rs': rust_storage,
    BASE+'content/browser/ad_block_service.h': service_header,
    BASE+'content/browser/ad_block_service.cc': service_cc,
}

def apply(core):
    # Transform every file in memory first: a missing anchor leaves no partial patch.
    outputs={path: fn((core/path).read_text()) for path,fn in TRANSFORMS.items()}
    for path,data in outputs.items():
        target=core/path
        if target.read_text()!=data:
            target.write_text(data)
    print('SANDIUM_ADBLOCK_RESOURCES=PASS bootstrap=noop_only last_good=validated snapshot=DAT_with_resources')

def main():
    if len(sys.argv)!=2:
        raise SystemExit('usage: apply-sandium-adblock-resources.py <brave-core>')
    core=Path(sys.argv[1]).resolve()
    actual=subprocess.check_output(['git','-C',str(core),'rev-parse','HEAD'],text=True).strip()
    if actual!=PIN:
        raise SystemExit('resource patch requires pinned Brave core '+PIN)
    apply(core)

if __name__=='__main__':
    main()
