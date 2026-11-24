"""Native host regression for exact observed selectors across both engine layers."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import observed_full_engines as d
import seal

ROOT = Path(__file__).resolve().parents[1]


class ObservedFullEngines(unittest.TestCase):
    def inputs(self):
        recipe = json.loads((ROOT / seal.RECIPE).read_bytes())['files']
        active = {}
        for owner in d.OWNERS:
            digest = recipe[owner]['after_sha256']
            data = (ROOT / seal.IMAGE / digest).read_bytes()
            self.assertEqual(seal.digest(data), digest)
            active[owner] = data.decode()
        return recipe, active

    def test_active_recipe_and_existing_protected_route(self):
        r, active = self.inputs()
        factory = active[d.FACTORY]
        b = factory.index('StyleForObservedEngineKeys(')
        engine = factory[b:factory.index('  Action Evaluate(', b)]
        for guard in ('Index::ValidObservedKeys(observed)', 'SensitiveCompoundPath(',
                      'url.DomainIs("thehindu.com")', 'url.DomainIs("tinypass.com")',
                      'url.DomainIs("piano.io")', '!primary_policy || !additional_policy',
                      'hidden_class_id_selectors(', 'Index::kMaxObservedResults'):
            self.assertIn(guard, engine)
        for obsolete in ('packaged_dom_index_', 'pending_dom_index_rules_', 'packaged_index_attempted_'):
            self.assertNotIn(obsolete, factory)
        old_blob = (ROOT / seal.IMAGE / d.OWNERS[d.FACTORY]).read_bytes()
        self.assertEqual(seal.digest(old_blob), d.OWNERS[d.FACTORY])
        old = old_blob.decode()
        expected_header = (ROOT / seal.IMAGE / d.OWNERS[d.GENERIC]).read_bytes()
        expected_generic = d.transform(d.GENERIC, expected_header).decode()
        current_header = active[d.GENERIC].replace(
            '#include "components/sandium_adblock/observed_ad_conjunction.h"\n', '', 1)
        # The independent closed conjunction grammar extends only the tail
        # after the prior simple selector intersection and fixed budgets.
        change_start = current_header.index('    auto css = batch.MatchCss(')
        change_end = current_header.index('    return css;', change_start) + len('    return css;')
        prior = expected_generic.index('    return batch.MatchCss(')
        prior_end = expected_generic.index(');', prior) + len(');')
        self.assertIn('const PackagedGenericDomIndex batch', current_header[:change_start])
        self.assertEqual(current_header[:change_start] +
                         expected_generic[prior:prior_end] +
                         current_header[change_end:], expected_generic)
        # The independent passive actions add another Install-side matcher
        # and adjacent methods; the only new observed worker body change is
        # the bounded pass-through into the closed C++ intersection. Network
        # and other observed policy remain the exact reviewed source.
        def method(text, signature, close):
            idx = text.index(signature)
            return text[idx:text.index(close, idx) + len(close)]
        transformed = d.transform(d.FACTORY, old_blob).decode()
        for signature in ('  std::optional<std::string> StyleForObservedEngineKeys(',
                          '  Action Evaluate('):
            actual_method = method(factory, signature, '\n  }')
            expected_method = method(transformed, signature, '\n  }')
            if signature.startswith('  std::optional'):
                old_hit = expected_method.index('            // Reject complex,')
                old_end = expected_method.index('\n          }\n', old_hit)
                new_hit = actual_method.index('            // Do not serialize a Rust hit')
                new_end = actual_method.index('\n          }\n', new_hit)
                self.assertIn('if (hit.size() <= 160)', actual_method[new_hit:new_end])
                self.assertEqual(actual_method[:new_hit] + actual_method[new_end:],
                                 expected_method[:old_hit] + expected_method[old_end:])
            else:
                self.assertEqual(actual_method, expected_method)
        before = factory.index('  std::string Style(GURL url)')
        after = factory.index('  // The browser requests only bounded keys', before)
        start = old.index('  std::string Style(GURL url)')
        end = old.index('  // This detached adapter', start)
        self.assertEqual(factory[before:after], old[start:end])  # untouched static lane
        signature = 'bool QueryObservedPackagedStyles('
        self.assertEqual(method(factory, signature, '\n}'),
                         method(old, signature, '\n}').replace(
                             'StyleForObservedPackagedKeys',
                             'StyleForObservedEngineKeys'))
        browser_path = 'chrome/browser/chrome_content_browser_client.cc'
        browser = (ROOT / seal.IMAGE / r[browser_path]['after_sha256']).read_text()
        self.assertIn('#define RAWS_EXPERIMENTAL_GENERIC_COSMETICS 1', browser)
        self.assertIn('QueryObservedPackagedStyles(', browser)

    def test_exact_native_policy_on_late_keys_failures_and_exceptions(self):
        cxx = shutil.which('c++')
        if cxx is None:
            self.skipTest('C++ compiler absent')
        recipe, active = self.inputs()
        cc = (ROOT / seal.IMAGE / recipe['components/sandium_adblock/generic_style.cc']
              ['after_sha256']).read_bytes()
        fixture = r'''#include "generic_style.h"
#include <cassert>
#include <map>

int main() {
  using namespace sandium::port1442;
  using Index = PackagedGenericDomIndex;
  using Results = std::optional<std::vector<std::string>>;
  // Model two fully admitted independent engines. Include enough prior entries
  // to put the actual observed fixture beyond both existing static ceilings.
  std::set<std::string> full_packaged, full_additional;
  std::string raw_subscription;
  for (int i = 0; i < 2600; ++i) {
    full_packaged.insert(".packaged" + std::to_string(i));
    full_additional.insert("#subscribed" + std::to_string(i));
    raw_subscription.append("###subscribed" + std::to_string(i) + "\n");
  }
  SimpleGenericCensus static_census(kSubscriptionGenericCandidateLimit);
  static_census.AddList(raw_subscription, kSubscriptionGenericPerList);
  auto early = static_census.Resolve([](const auto&, const auto& ids) {
    std::vector<std::string> found;
    for (const auto& id : ids) found.push_back("#" + id);
    return found;
  });
  assert(std::ranges::find(early, "#subscribed2550") == early.end());
  int calls = 0;
  bool primary_failed = false, additional_overflow = false, additional_failed = false;
  Index::ScopePolicy base{false, {}}, sub{false, {"#subscribed2552"}};
  Index::Keys keys{{"packaged2551", "packaged2550", "subscribed2550"},
                   {"subscribed2550", "subscribed2552"}};
  auto query = [&](bool packaged, const Index::Keys& observed,
                   const std::vector<std::string>& exceptions) -> Results {
    ++calls;
    assert(exceptions == std::vector<std::string>{"#subscribed2552"});
    if ((packaged && primary_failed) || (!packaged && additional_failed)) {
      return std::nullopt;
    }
    if (!packaged && additional_overflow) {
      return std::vector<std::string>(Index::kMaxObservedResults+1,"#subscribed2550");
    }
    auto& all = packaged ? full_packaged : full_additional;
    // Deliberately feed extra/complex/scope-exempt engine candidates. No raw CSS
    // and no wrong typed key may slip through the exact-key intersection.
    std::vector<std::string> matched{"#unobserved", ".packaged2550 > div",
                                     "#subscribed2552", ".invented, main"};
    for (const auto& key : observed.ids) {
      if (all.contains("#"+key)) matched.push_back("#"+key);
    }
    for (const auto& key : observed.classes) {
      if (all.contains("."+key)) matched.push_back("."+key);
    }
    return matched;
  };
  auto both = Index::MatchObservedEngineCss(keys, base, sub, query);
  assert(both && calls == 2);
  assert(both->find(".packaged2550") != std::string::npos);
  assert(both->find(".packaged2551") != std::string::npos);
  assert(both->find("#subscribed2550") != std::string::npos);
  assert(both->find("subscribed2552") == std::string::npos);
  assert(both->find(".subscribed2550") == std::string::npos);
  assert(both->find("unobserved") == std::string::npos);
  assert(both->find("> div") == std::string::npos);
  assert(both->find("invented") == std::string::npos);
  primary_failed = true;
  auto one = Index::MatchObservedEngineCss(keys, base, sub, query);
  assert(one && one->find("#subscribed2550") != std::string::npos);
  assert(one->find(".packaged2550") == std::string::npos);
  primary_failed = false;
  additional_overflow = true;
  auto overflow = Index::MatchObservedEngineCss(keys, base, sub, query);
  assert(overflow && overflow->find(".packaged2550") != std::string::npos);
  assert(overflow->find("#subscribed2550") == std::string::npos);
  additional_overflow = false;
  primary_failed = additional_failed = true;
  assert(!Index::MatchObservedEngineCss(keys, base, sub, query));
  calls = 0;
  sub.suppress_generic = true;
  assert(Index::MatchObservedEngineCss(keys, base, sub, query)->empty() && calls == 0);
  sub.suppress_generic = false;
  assert(!Index::MatchObservedEngineCss({{"toolbar,main"}, {}}, base, sub, query));
  assert(!Index::MatchObservedEngineCss({std::vector<std::string>(65, "over"), {}},
                                        base, sub, query) && calls == 0);
}
'''
        with tempfile.TemporaryDirectory() as path:
            temp = Path(path)
            (temp / 'generic_style.h').write_text(active[d.GENERIC])
            (temp / 'generic_style.cc').write_bytes(cc)
            grammar = 'components/sandium_adblock/observed_ad_conjunction.h'
            (temp / grammar).parent.mkdir(parents=True)
            payload = (ROOT / seal.IMAGE / recipe[grammar]['after_sha256']).read_bytes()
            self.assertEqual(recipe[grammar]['after_sha256'], seal.digest(payload))
            (temp / grammar).write_bytes(payload)
            (temp / 'test.cc').write_text(fixture)
            subprocess.run([cxx, '-std=c++23', '-Wall', '-Wextra', '-Werror',
                            '-I'+str(temp), str(temp/'test.cc'), str(temp/'generic_style.cc'),
                            '-o', str(temp/'fixture')], check=True)
            subprocess.run([str(temp/'fixture')], check=True)


if __name__ == '__main__':
    unittest.main()
