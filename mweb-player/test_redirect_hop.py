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
