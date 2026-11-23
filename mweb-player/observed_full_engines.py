"""Use both admitted native engines for bounded observed generic DOM keys."""
import argparse
from pathlib import Path

from glue import once
import seal

BASE = 'db4c099f740be73708e4c668c91288430b0b5af4'
MAN = '3b955b4cddb92dcc0064b000de8cfa9a23e69c7e66a3bbd19e643a21f091f948'
PROOF = 'f1e9a7deede0f087657d74b5fee517e28cc2b8d648d68f6c4c97975a21569e4d'
FACTORY = 'components/sandium_adblock/document_subresource_factory.cc'
GENERIC = 'components/sandium_adblock/generic_style.h'
OWNERS = {
    FACTORY: '5ad05cc0d5d7b23e52b44a2b4924b5a6bb7de2105cc8907fd04933de693e7f29',
    GENERIC: '286acf02e555654c79830f7ac9d3710b5b133879372e303d20cd02c61656faaf',
}


def transform(path, original):
    s = original.decode()
    if path == FACTORY:
        s = once(s, '    pending_dom_index_rules_ = std::move(text);\n', '')
        s = once(s, '''  // This detached adapter is called only for a validated native page request.
  // Initialize lazily so the existing startup/readiness flow is unchanged
  // until a browser caller deliberately activates this path.
  std::optional<std::string> StyleForObservedPackagedKeys(''',
                 '''  // The browser requests only bounded keys from a validated live document.
  // Query the same admitted engines as ordinary scoped CSS, avoiding a global
  // precomputed census or retained package text on this dynamic path.
  std::optional<std::string> StyleForObservedEngineKeys(''')
        start = '    if (!packaged_dom_index_) {'
        end = '    const auto policy = '
        s = once(s, s[s.index(start):s.index(end)], '')
        start = '    // The exact Android Sandium donor maps Shield On to Aggressive.'
        end = '\n  }\n\n  Action Evaluate'
        s = once(s, s[s.index(start):s.index(end, s.index(start))], '''    return Index::MatchObservedEngineCss(
        observed, *primary_policy, *additional_policy,
        [&](bool packaged, const Index::Keys& keys,
            const std::vector<std::string>& exceptions)
            -> std::optional<std::vector<std::string>> {
          const adblock::Engine& engine = packaged ? **primary_ : **additional_;
          auto result = engine.hidden_class_id_selectors(
              keys.classes, keys.ids, exceptions);
          if (result.result_kind != adblock::ResultKind::Success ||
              result.value.size() > Index::kMaxObservedResults) {
            return std::nullopt;
          }
          std::vector<std::string> matches;
          for (const auto& hit : result.value) {
            // Reject complex, overlong and unrelated engine candidates at the
            // bounded intersection, not as raw CSS from a filter list.
            if (std::string_view candidate(hit.data(), hit.size());
                ::sandium::port1442::IsSimpleGenericSelector(candidate)) {
              matches.emplace_back(candidate);
            }
          }
          return matches;
        });''')
        s = once(s, '''  std::optional<::sandium::port1442::PackagedGenericDomIndex> packaged_dom_index_;
  bool packaged_index_attempted_ = false;
  std::string pending_dom_index_rules_;
''', '')
        s = once(s, '  state.snapshot.AsyncCall(&RuleSnapshot::StyleForObservedPackagedKeys)',
                    '  state.snapshot.AsyncCall(&RuleSnapshot::StyleForObservedEngineKeys)')
    elif path == GENERIC:
        anchor = ' private:\n  explicit PackagedGenericDomIndex(std::vector<std::string> selectors);'
        s = once(s, anchor, '''  // Both inputs are the live snapshot's complete Rust engines, not a
  // packaged text index or an enabled-list per-list census. Bound each reply
  // independently so one failing engine cannot drop the other's safe hits.
  template <typename Query>
  static std::optional<std::string> MatchObservedEngineCss(
      const Keys& observed,
      const ScopePolicy& packaged_policy,
      const ScopePolicy& additional_policy,
      Query query) {
    if (!ValidObservedKeys(observed)) return std::nullopt;
    if (packaged_policy.suppress_generic || additional_policy.suppress_generic ||
        (observed.classes.empty() && observed.ids.empty())) {
      return std::string();
    }
    const auto exceptions = ObservedExceptions(
        observed, packaged_policy, additional_policy);
    auto packaged = query(/*packaged=*/true, observed, exceptions);
    auto additional = query(/*packaged=*/false, observed, exceptions);
    const auto oversized = [](const auto& matches) {
      return matches && matches->size() > kMaxObservedResults;
    };
    if (oversized(packaged)) packaged.reset();
    if (oversized(additional)) additional.reset();
    if (!packaged && !additional) return std::nullopt;

    // Reuse the existing exact typed-key intersection and fixed declaration;
    // this temporary holds only the bounded matches for one observed batch.
    std::vector<std::string> primary_hits;
    if (packaged) {
      primary_hits = std::move(*packaged);
      std::sort(primary_hits.begin(), primary_hits.end());
    }
    const PackagedGenericDomIndex batch(std::move(primary_hits));
    return batch.MatchCss(observed, &packaged_policy, &additional_policy,
                          additional ? *additional
                                     : std::vector<std::string>{});
  }

'''+anchor)
    else:
        raise ValueError(path)
    return s.encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if Path.cwd() != Path(__file__).resolve().parents[1]:
        raise ValueError('run in checkout root')
    read = lambda name: seal.git('show', BASE + ':' + name)
    out = seal.plan(read, owners=OWNERS, edit=transform, man=MAN, proof=PROOF)
    if args.write:
        if seal.git('rev-parse', 'HEAD').decode().strip() != BASE:
            raise ValueError('wrong checkout')
        for name, data in out.items():
            p = Path(name)
            if p.is_symlink() or (p.exists() and p.read_bytes() !=
                    (data if name.startswith(seal.IMAGE) else read(name))):
                raise ValueError('dirty or unsafe overlay path: ' + name)
    for name, data in sorted(out.items()):
        if args.write:
            Path(name).write_bytes(data)
        print(seal.digest(data), name)


if __name__ == '__main__':
    main()
