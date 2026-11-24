"""Run the materialized redirect-hop code with narrow Chromium API doubles."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent
OWNER = 'components/sandium_adblock/document_subresource_factory.cc'
RECIPE = ROOT / 'raws-adblock/production-restore-recipe.json'


def factory():
    sha = json.loads(RECIPE.read_text())['files'][OWNER]['after_sha256']
    data = (ROOT / 'raws-adblock/production-postimages' / sha).read_bytes()
    if hashlib.sha256(data).hexdigest() != sha:
        raise ValueError('factory hash does not match recipe')
    return data.decode()


class RedirectHopTest(unittest.TestCase):
    def test_redirect_callbacks_include_complete_mojo_structs(self):
        source = factory()
        for mojom, name in (('early_hints', 'EarlyHints'),
                            ('url_response_head', 'URLResponseHead')):
            self.assertIn(f'network::mojom::{name}Ptr', source)
            self.assertIn(f'#include "services/network/public/mojom/{mojom}.mojom.h"', source)

    def test_merged_attachment_leaves_early_native_path_alone(self):
        source = factory()
        initial = source[source.index('class RequestFactory final'):
                         source.index('  void Finish(', source.index('class RequestFactory final'))]
        finish = source[source.index('  void Finish(', source.index('class RequestFactory final')):
                        source.index('  const ScopedUserRuleQuery scoped_user_rules_;')]
        self.assertIn('downstream_->CreateLoaderAndStart', initial)
        self.assertNotIn('ScopedRedirectHop::Start', initial)
        self.assertEqual(finish.count('ScopedRedirectHop::Start'), 1)
        self.assertIn('site_gate_.Run()', finish)
        self.assertIn("request.trusted_params || request.request_body", initial)
        self.assertIn("loader.is_valid() && client.is_valid()", finish)
        self.assertEqual(source.count('&RuleSnapshot::StyleForObservedEngineKeys'), 1)

    def test_object_factory_and_decision_match_without_widening_methods(self):
        source = factory()
        gate = source[source.index('std::optional<Resource> GetResourceType'):
                      source.index('class ScopedUserRulesSnapshot')]
        owner = 'components/sandium_adblock/subresource_decision.cc'
        sha = json.loads(RECIPE.read_text())['files'][owner]['after_sha256']
        data = (ROOT / 'raws-adblock/production-postimages' / sha).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), sha)
        from test_request_gate import H
        bridge = H.replace('kFontResource,kMainFrame',
                           'kFontResource,kMainFrame,kObject')
        bridge = bridge.replace('inline unsigned calls=0;',
                                'inline unsigned calls=0; inline bool deny=false;')
        bridge = bridge.replace('bool blocked()const{return false;}',
                                'bool blocked()const{return deny;}')
        bridge = bridge.replace('bool SchemeIsHTTPOrHTTPS()const{return true;}',
                                'bool SchemeIsHTTPOrHTTPS()const{return path.starts_with("https://");}')
        fixture = r"""
#include <cassert>
int main() {
  using namespace sandium::adblock_native;
  using T = blink::mojom::ResourceType;
  const auto object = GetResourceType(static_cast<int>(T::kObject));
  assert(object == T::kObject);
  assert(!GetResourceType(static_cast<int>(T::kMainFrame)));
  assert(!GetResourceType(static_cast<int>(T::kSubFrame)));
  const GURL url{"https://third-party.test/embedded"};
  const url::Origin initiator;
  const adblock::Engine engine;
  for (const auto* method : {"GET", "HEAD", "POST", "OPTIONS"}) {
    const bool eligible = std::string_view(method) == "GET" ||
                          std::string_view(method) == "HEAD";
    calls = 0;
    assert(DecideDocumentSubresource(&engine, &engine, url, *object, initiator,
                                    method) ==
           (eligible ? SubresourceAction::kAllow :
                       SubresourceAction::kNotEvaluated));
    assert(calls == (eligible ? 1u : 0u));
  }
  deny = true;
  assert(DecideDocumentSubresource(&engine, &engine, url, *object, initiator,
                                  "GET") == SubresourceAction::kBlock);
  deny = false;
  assert(DecideDocumentSubresource(&engine, &engine,
      GURL{"https://first-party.test/document.pdf"}, *object, initiator, "GET") ==
      SubresourceAction::kAllow);
  calls = 0;
  assert(DecideDocumentSubresource(&engine, &engine,
      GURL{"chrome-extension://viewer/index.html"}, *object, initiator, "GET") ==
      SubresourceAction::kNotEvaluated);
  assert(calls == 0);
}
"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            header = root / 'components/sandium_adblock/subresource_decision.h'
            header.parent.mkdir(parents=True)
            header.write_text(bridge)
            src = root / 'test.cc'
            binary = root / 'test'
            src.write_text(data.decode() +
                           '\n#include <optional>\n#include <string_view>\n' +
                           'using Resource = blink::mojom::ResourceType;\n' +
                           gate + fixture)
            subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                            '-I', td, str(src), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True, cwd=td)

    def test_exact_proxy_timeout_block_lifetime_and_native_passthrough(self):
        source = factory()
        seam = source[source.index('class ScopedRedirectHop final'):
                      source.index('class RequestFactory final')]
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / 'test.cc'
            binary = Path(td) / 'test'
            src.write_text((FIXTURE / 'redirect_hop_host_stubs.inc').read_text()
                           + '\n#define private public\n' + seam + '\n#undef private\n'
                           + (FIXTURE / 'redirect_hop_host_cases.inc').read_text())
            subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                            str(src), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
