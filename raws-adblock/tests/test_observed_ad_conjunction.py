"""Host checks executing exact worker policy, browser CSS accumulator and renderer guard."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMP = 'components/sandium_adblock/'
BROWSER = 'chrome/browser/chrome_content_browser_client.cc'
FACTORY = COMP + 'document_subresource_factory.cc'
RENDERER = 'chrome/renderer/chrome_render_frame_observer.cc'
MANIFEST = json.loads((ROOT / 'production-restore-recipe.json').read_bytes())['files']


def owner(path):
    digest = MANIFEST[path]['after_sha256']
    data = (ROOT / 'production-postimages' / digest).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(path)
    return data.decode()


def cut(text, start, end):
    begin = text.index(start)
    return text[begin:text.index(end, begin)]


class ObservedAdConjunction(unittest.TestCase):
    def test_worker_accumulator_renderer_runtime(self):
        cxx = shutil.which('c++')
        if not cxx:
            self.skipTest('c++ not available')
        tmp_root = ROOT.parent
        with tempfile.TemporaryDirectory(dir=tmp_root) as name:
            path = Path(name)
            for relative in (COMP + 'generic_style.h', COMP + 'generic_style.cc',
                             COMP + 'observed_ad_conjunction.h'):
                out = path / relative
                out.parent.mkdir(parents=True, exist_ok=True)
                try:
                    out.write_text(owner(relative))
                except KeyError:
                    # Baseline has no added grammar; its worker and guards do
                    # not include it. Allows exercising before and after.
                    if not relative.endswith('observed_ad_conjunction.h'):
                        raise
            browser = cut(owner(BROWSER),
                          'namespace sandium::adblock_native::observed_generic {',
                          '}  // namespace sandium::adblock_native::observed_generic')
            renderer = cut(owner(RENDERER), 'constexpr size_t kRawSGenericRecords = 64;',
                           'std::vector<uint8_t> PackRawSGenericDiscoveryRound(')
            renderer += cut(owner(RENDERER), 'std::optional<std::string> RawSGuardObservedGenericStyle(',
                            'WebLocalFrame* RawSGenericDiscoveryFrame(')
            apply_styles = cut(owner(RENDERER),
                'void ChromeRenderFrameObserver::ApplyRawSObservedGenericStyles(',
                'void ChromeRenderFrameObserver::ApplyRawSHideStyles(')
            fixture = r'''
#include <cassert>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <set>
#include <span>
#include <string_view>
#include "components/sandium_adblock/generic_style.h"
''' + browser + '}\n' + renderer + r'''
// The test starts at Chromium's stylesheet application entry point. The
// linked Blink/IPC implementation is replaced only at this DOM boundary.
namespace base {
using UnguessableToken = int;
}
using GURL = std::string;
namespace blink {
struct WebString {
  static std::string FromUtf8(std::string_view value) { return std::string(value); }
};
enum class WebCssOrigin { kUser };
}
struct Document {
  std::string* sheet;
  std::string_view Url() { return "https://fixture.test/current"; }
  void RemoveInsertedStyleSheet(const std::string& key, blink::WebCssOrigin) {
    assert(key == "sandium-observed-generic-rules-v1");
    sheet->clear();
  }
  void InsertStyleSheet(std::string style, const std::string* key, blink::WebCssOrigin) {
    assert(*key == "sandium-observed-generic-rules-v1");
    *sheet = std::move(style);
  }
};
struct Frame {
  std::string sheet;
  Document GetDocument() { return Document{&sheet}; }
};
Frame* RawSGenericDiscoveryFrame(Frame* frame, base::UnguessableToken token) {
  return token == 1 ? frame : nullptr;
}
struct ChromeRenderFrameObserver {
  Frame frame;
  Frame* render_frame() { return &frame; }
  void ApplyRawSObservedGenericStyles(
      const base::UnguessableToken&, const GURL&, const std::string&);
};
''' + apply_styles + r'''
using Index = sandium::port1442::PackagedGenericDomIndex;
using sandium::adblock_native::observed_generic::StyleAccumulator;

int main(int argc, char** argv) {
  assert(argc == 3);
  const std::string_view mode(argv[2]);
  if (mode == "browser") {
    StyleAccumulator accumulation;
    assert(accumulation.Accept(".ad.layout { display:none !important; }\n"));
    return 0;
  }
  if (mode == "renderer") {
    assert(RawSGuardObservedGenericStyle(".ad.layout { display:none !important; }\n"));
    return 0;
  }
  Index::ScopePolicy allow{false, {}};
  Index::ScopePolicy exact_exception{false, {".sponsor.ad"}};
  Index::ScopePolicy disabled{true, {}};
  Index::Keys observed{{"ad", "sponsor", "layout"}, {"leaderboard"}};
  if (mode == "many-late-additions") {
    StyleAccumulator accumulation;
    ChromeRenderFrameObserver page;
    const GURL current = "https://fixture.test/current";
    const auto& applied = page.frame.sheet;
    auto observe_run = [&](unsigned from, unsigned to) {
      for (unsigned i = from; i < to; ++i) {
        const std::string id = std::to_string(i);
        const std::string token =
            i % 6 == 0 ? ".a" + id :
            i % 6 == 1 ? ".ad.b" + id :
            i % 6 == 2 ? ".ad.c" + id + ".another" :
            i % 6 == 3 ? "#d" + id :
            i % 6 == 4 ? "#e" + id + ".ad" :
                         "#f" + id + ".ad.another";
        const size_t prior = accumulation.css().size();
        assert(accumulation.Accept(token + " { display:none !important; }\n"));
        assert(accumulation.css().size() > prior);
        // Verify actual update decisions while additions arrive well after
        // the renderer's old one-wrapper-per-selector ceiling.
        if (i % 43 == 42 || i + 1 == to) {
          page.ApplyRawSObservedGenericStyles(1, current, accumulation.css());
          assert(applied.find(token) != std::string::npos &&
                 "must replace old stylesheet after a late update");
          assert(applied.size() <= 512 * 1024);
        }
      }
    };
    observe_run(0,128);
    observe_run(128,4096);
    assert(applied.find(".a0") != std::string::npos);
    assert(applied.find("#d4095") != std::string::npos);
    const auto last = accumulation.css();
    assert(!accumulation.Accept(".ad.extra-limit-test { display:none !important; }\n"));
    assert(accumulation.css() == last);
    // Accepted renderer output stays coherent, and the browser's normal
    // revocation path supplies the empty next sheet.
    accumulation = {};
    page.ApplyRawSObservedGenericStyles(2, current, accumulation.css());
    assert(!applied.empty());  // Wrong document token can't remove user CSS.
    page.ApplyRawSObservedGenericStyles(1, current, accumulation.css());
    assert(applied.empty());
    assert(accumulation.Accept(".replacement { display:none !important; }\n"));
    page.ApplyRawSObservedGenericStyles(1, "https://fixture.test/stale", accumulation.css());
    assert(applied.empty());
    page.ApplyRawSObservedGenericStyles(1, current, accumulation.css());
    assert(applied.find(".replacement") != std::string::npos);
    assert(applied.find("#d4095") == std::string::npos);

    // Many long conjunctions can hit the unchanged ungrouped-byte budget
    // before the entry count. A smaller packed sheet must not expand it.
    StyleAccumulator long_selectors;
    size_t original_bytes = 0;
    bool rejected_at_byte_cap = false;
    for (unsigned i = 0; i < 2500; ++i) {
      const std::string line = ".ad." + std::string(56, 'b') +
          std::to_string(i) + "." + std::string(60, 'c') +
          " { display:none !important; }\n";
      const auto pre = long_selectors.css();
      const bool admitted = long_selectors.Accept(line);
      if (original_bytes + line.size() > 256 * 1024) {
        assert(!admitted && long_selectors.css() == pre);
        rejected_at_byte_cap = true;
        break;
      }
      assert(admitted);
      original_bytes += line.size();
    }
    assert(rejected_at_byte_cap);
    return 0;
  }
  if (mode == "specificity-groups") {
    StyleAccumulator accumulation;
    for (const auto& selector : {".b", ".a", ".ad.layout", ".ad.item",
                                 ".ad.ship.site", "#block", "#extra",
                                 "#pub.ad", "#ticker.ad.item"})
      assert(accumulation.Accept(std::string(selector) + " { display:none !important; }\n"));
    assert(accumulation.css() ==
           ".a,.b { display:none !important; }\n"
           ".ad.item,.ad.layout { display:none !important; }\n"
           ".ad.ship.site { display:none !important; }\n"
           "#block,#extra { display:none !important; }\n"
           "#pub.ad { display:none !important; }\n"
           "#ticker.ad.item { display:none !important; }\n");
    assert(!RawSGuardObservedGenericStyle(".a,#extra { display:none !important; }\n"));
    assert(!RawSGuardObservedGenericStyle(".ad,.ad.layout { display:none !important; }\n"));
    const auto grouped = RawSGuardObservedGenericStyle(accumulation.css());
    assert(grouped && grouped->find(":is(.a,.b):where(div,aside,section,ins):not(")
                        != std::string::npos);
    assert(grouped->find(":is(#block,#extra):where(div,aside,section,ins):not(")
                        != std::string::npos);
    return 0;
  }
  if (mode == "ordered-exceptions") {
    const auto reordered = [&](bool packaged, const auto&, const auto&) {
      if (packaged)
        return std::optional(std::vector<std::string>{
            ".ad.layout", ".layout.ad", "#leaderboard.ad.layout"});
      return std::optional(std::vector<std::string>{
          ".layout.ad#leaderboard", ".layout.ad.other"});
    };
    Index::ScopePolicy token{false, {".ad"}};
    auto any_token = Index::MatchObservedEngineCss(observed, token, allow, reordered);
    assert(any_token && any_token->empty() && "ad token vetoes either anchor order");
    Index::ScopePolicy compound{false, {".ad#leaderboard.layout", ".layout.ad"}};
    auto permutation = Index::MatchObservedEngineCss(observed, allow, compound, reordered);
    assert(permutation && permutation->find(".ad.layout {") == std::string::npos);
    assert(permutation->find(".layout.ad {") == std::string::npos);
    assert(permutation->find("#leaderboard.ad.layout {") == std::string::npos);
    assert(permutation->find(".layout.ad#leaderboard {") == std::string::npos);
    assert(permutation->find(".layout.ad.other {") != std::string::npos);
    auto no_anchor = Index::MatchObservedEngineCss({{"ad"}, {}}, allow, allow, reordered);
    assert(no_anchor && no_anchor->find(".ad.layout {") != std::string::npos);
    assert(no_anchor->find(".layout.ad {") == std::string::npos);
    return 0;
  }
  const auto query = [&](bool packaged, const auto&, const auto&) {
    if (packaged)
      return std::optional(std::vector<std::string>{
        ".ad", ".ad.layout", ".unobserved.ad", ".ad::before", ".ad#ad#ad",
        ".ad .something", ".ad[id]", ".ad.layout{color:red}", ".ad.layout,.body",
        ".ad.ad", ".ad.abc.ghi.def", ".sponsor.ad", "#leaderboard.ad"
      });
    return std::optional(std::vector<std::string>{
      ".ad.layout", ".ad.unit", ".ad.normal-ad[aria-label='local']", ".sponsor.ad"
    });
  };
  auto complete = Index::MatchObservedEngineCss(observed, allow,
                                                 exact_exception, query);
  assert(complete && complete->find(".ad {") != std::string::npos);
  assert(complete->find(".ad.layout {") != std::string::npos);
  assert(complete->find(".ad.unit {") != std::string::npos);
  assert(complete->find("#leaderboard.ad {") != std::string::npos);
  for (auto untrusted : {".unobserved", ".sponsor.ad", "::before",
                          ".ad#ad", ".ad .something", "[id]", "color:red",
                          ",.body", ".ad.ad", ".ad.abc.ghi.def", "[aria-label"})
    assert(complete->find(untrusted) == std::string::npos);
  Index::ScopePolicy key_exception{false, {".ad"}};
  auto suppressed_key = Index::MatchObservedEngineCss(
      observed, key_exception, exact_exception, query);
  assert(suppressed_key && suppressed_key->find(".ad.layout") == std::string::npos);
  auto suppressed = Index::MatchObservedEngineCss(observed, disabled, allow, query);
  assert(suppressed && suppressed->empty());

  StyleAccumulator accumulator;
  assert(accumulator.Accept(*complete));
  const auto initial = accumulator.css();
  assert(accumulator.Accept(*complete) && accumulator.css() == initial);
  assert(!accumulator.Accept(".ad.layout:has(a) { display:none !important; }\n"));
  assert(accumulator.css() == initial);
  auto css = RawSGuardObservedGenericStyle(initial);
  assert(css && css->find(".ad.layout") != std::string::npos);
  assert(css->find(":where(div,aside,section,ins)") != std::string::npos);
  // Exact authorized wrappers remain on the new shape. Chromium CSS parsing
  // and measured rendering of this output are not part of this C++ fixture.
  assert(css->find(":not(:has(:is(a,button,dialog") != std::string::npos);
  assert(css->find("[class*=\"paywall\" i]") != std::string::npos);
  assert(css->find(":is(article,main,header,footer,nav,h1") != std::string::npos);
  assert(!RawSGuardObservedGenericStyle(".ad.layout{color:red} { display:none !important; }\n"));
  assert(!RawSGuardObservedGenericStyle(".unit.news { display:none !important; }\n"));

  std::ifstream list(argv[1]);
  assert(list);
  std::set<std::string> hits;
  for (std::string line; std::getline(list, line);) {
    if (line.starts_with("##") &&
        !sandium::adblock_native::observed_cosmetic::AdConjunctionKey(
             std::string_view(line).substr(2)).empty() &&
        sandium::port1442::ParseAdCompound(std::string_view(line).substr(2))
             .first.empty())
      hits.insert(line);
  }
  assert(hits.size() == 62);
}
'''
            if COMP + 'observed_ad_conjunction.h' not in MANIFEST:
                fixture = fixture[:fixture.index('  std::ifstream list(')] + '  (void)argv;\n}\n'
            code = path / 'fixture.cc'
            code.write_text(fixture)
            exe = path / 'fixture'
            subprocess.run([cxx, '-std=c++20', '-Wall', '-Wextra', '-Werror',
                            '-I', str(path), str(code),
                            str(path / (COMP + 'generic_style.cc')),
                            '-o', str(exe)], check=True)
            packaged = ROOT / 'production-postimages' / MANIFEST[
                'chrome/browser/resources/raws/easylist.txt']['after_sha256']
            for mode in ('worker', 'browser', 'renderer', 'ordered-exceptions',
                         'many-late-additions', 'specificity-groups'):
                with self.subTest(mode=mode):
                    subprocess.run([str(exe), str(packaged), mode], check=True)

    def test_worker_route_and_renderer_document_guards_unchanged(self):
        body = cut(owner(FACTORY), 'StyleForObservedEngineKeys(',
                   'uint32_t QueryReviewedPassiveScriptlets(')
        for guard in ('Index::ValidObservedKeys(observed)', 'SensitiveCompoundPath(',
                      'kMaxObservedResults', 'MatchObservedEngineCss('):
            self.assertIn(guard, body)
        target = cut(owner(RENDERER), 'void ChromeRenderFrameObserver::ApplyRawSObservedGenericStyles(',
                     'void ChromeRenderFrameObserver::ApplyRawSHideStyles(')
        self.assertIn('GURL(doc.Url()) != expected_url', target)
        self.assertIn('RawSGenericDiscoveryFrame(render_frame(), token)', target)
        self.assertIn('RawSGuardObservedGenericStyle(css)', target)
