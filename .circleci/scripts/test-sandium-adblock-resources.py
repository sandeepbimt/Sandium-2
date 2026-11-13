#!/usr/bin/env python3
"""Offline source-contract tests. Does not claim native/runtime execution."""
import base64
import hashlib
import json
from pathlib import Path
import re
import runpy
import unittest

HERE=Path(__file__).resolve().parent
M=runpy.run_path(str(HERE/'apply-sandium-adblock-resources.py'))
FIXTURES=HERE.parent/'tests/resource-fixtures'

class ResourcesPatchTest(unittest.TestCase):
    def source(self,name):
        return (FIXTURES/name).read_text()

    def transformed(self, fn, name):
        out=M[fn](self.source(name))
        self.assertEqual(out,M[fn](out))
        return out

    def test_pinned_fixtures_integrity(self):
        provenance=json.loads((FIXTURES/'provenance.json').read_text())
        self.assertEqual(provenance['brave_core_sha'], M['PIN'])
        for name,row in provenance['files'].items():
            self.assertEqual(hashlib.sha256((FIXTURES/name).read_bytes()).hexdigest(),row['sha256'])

    def test_headers_and_bridge_idempotent(self):
        for fn,name in [('default_header','ad_block_default_resource_provider.h'),
                        ('custom_header','ad_block_custom_resource_provider.h'),
                        ('rust_bridge','lib.rs')]:
            self.transformed(fn,name)

    def test_noop_is_valid_unprivileged_own_script(self):
        cc=self.transformed('default_cc','ad_block_default_resource_provider.cc')
        encoded=re.search(r'R"json\((.*?)\)json"',cc).group(1)
        rows=json.loads(encoded)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['name'],'noop.js')
        self.assertEqual(rows[0]['kind'],{'mime':'application/javascript'})
        self.assertNotIn('permission',rows[0])
        self.assertEqual(base64.b64decode(rows[0]['content']),b'/* Sandium no-op script. */')
        self.assertNotIn('thehindu',cc.lower())
        self.assertIn('clone_resource_storage(*validated_storage_)',cc)
        self.assertNotIn('new_empty_resource_storage()',cc)

    def test_failed_update_does_not_mutate_current_bundle(self):
        cc=self.transformed('default_cc','ad_block_default_resource_provider.cc')
        body=cc.split('void AdBlockDefaultResourceProvider::OnResourcesRead(',1)[1]
        self.assertLess(body.index('generation != resource_generation_'),body.index('validated_storage_ ='))
        self.assertLess(body.index('resource_storage_json_is_valid'),body.index('validated_storage_ ='))
        self.assertLess(body.index('validated_storage_ ='),body.index('NotifyResourcesLoaded'))

    def test_rust_validation_uses_actual_parser_and_insertion(self):
        rs=self.transformed('rust_storage','resource_storage.rs')
        self.assertIn('serde_json::from_str::<Vec<Resource>>',rs)
        self.assertIn('resources.is_empty()',rs)
        self.assertIn('storage.add_resource(resource).is_ok()',rs)
        self.assertNotIn('dependencies.iter().all',rs)

    def test_custom_merge_generation_guards(self):
        cc=self.transformed('custom_cc','ad_block_custom_resource_provider.cc')
        self.assertEqual(cc.count('if (generation != resource_generation_)'),2)
        self.assertIn('weak_ptr_factory_.GetWeakPtr(), resource_generation_',cc)
        self.assertIn('weak_ptr_factory_.GetWeakPtr(), generation, std::move(on_load)',cc)
        self.assertIn('LoadResources(std::move(on_load));',cc)
        self.assertIn('!IsDeveloperModeEnabled(profile_prefs)',cc)
        self.assertIn('!IsValidResource(resource)',cc)

    def test_native_regressions_added_not_claimed_executed(self):
        cc=self.transformed('resource_tests','ad_block_custom_resource_provider_unittest.cc')
        for name in ['BootstrapNoopBeforeComponentReady','InvalidUpdatePreservesPreviousBundle','OlderReadCannotReplaceNewerResources','PartialBundleKeepsUpstreamSkipSemantics','ExistingAliasCannotBlockCanonicalBootstrap']:
            self.assertIn(name,cc)

    def test_dat_waits_for_resources_and_rejects_late_cache(self):
        cc='''uint64_t filter_set_generation_ = 0;
void AdBlockService::SourceProviderObserver::OnDATFileRead(
    DATFileDataBuffer dat) {
  on_resources_loaded_.Run(engine_is_default_, std::move(dat), nullptr,
                           adblock::new_empty_resource_storage());
  LoadResources(nullptr, filter_set_generation_);
}

void AdBlockService::SourceProviderObserver::OnFilterSetCreated(
    uint64_t generation) {}
'''
        out=M['service_cc'](cc)
        self.assertEqual(out,M['service_cc'](out))
        self.assertNotIn('new_empty_resource_storage()',out)
        self.assertIn('if (filter_set_generation_ != 0)',out)
        self.assertIn('if (generation != filter_set_generation_)',out)
        self.assertIn('OnDATResourcesLoaded',out)
        h=M['service_header']('    void OnDATFileRead(DATFileDataBuffer dat);')
        self.assertEqual(h,M['service_header'](h))

    def test_missing_anchor_fails(self):
        with self.assertRaises(RuntimeError):
            M['default_header']('wrong source')

if __name__=='__main__':
    unittest.main()
