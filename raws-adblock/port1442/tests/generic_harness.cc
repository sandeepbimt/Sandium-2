// SPDX-License-Identifier: MPL-2.0
#include "generic_style.h"
#include "style.h"

#include <cassert>
#include <chrono>
#include <fstream>
#include <iostream>
#include <iterator>

using namespace sandium::port1442;

int main(int argc, char** argv) {
  SimpleGenericCensus keys(5);
  assert(keys.AddList("##.ad-slot\n###ad-banner\r\n##.ad-slot\n"
                      "##.late-ad\n##.ignored-by-engine\n##-invalid\n"
                      "site.test##.scoped\nsite.test#@#.ad-slot\n"
                      "##.ad-slot,body\n##.ad-slot{color:red}\n"
                      "##.ad-slot strong\n##.ad-slot:has(.x)\n"
                      "##.ad-slot\\test\n##.脚本\n", 5) == 4);
  assert(!keys.AddList("##.has-limit\n", 0));
  auto packed = keys.Resolve([](const auto& classes, const auto& ids) {
    assert(classes == (std::vector<std::string>{"ad-slot", "late-ad", "ignored-by-engine"}));
    assert(ids == (std::vector<std::string>{"ad-banner"}));
    return std::vector<std::string>{"#ad-banner", ".ad-slot{color:red}",
                                    ".unknown-exact", ".ad-slot,body", ".late-ad", ".ad-slot"};
  });
  assert((packed == std::vector<std::string>{".ad-slot", "#ad-banner", ".late-ad"}));
  auto merged = MergeSimpleGeneric(std::move(packed), {".late-ad", "#new-banner", ".scoped"});
  assert((merged == std::vector<std::string>{".ad-slot", "#ad-banner", ".late-ad", "#new-banner", ".scoped"}));
  std::string css = HideStyles({".scoped"}, {});
  AppendSimpleGenericStyles(css, false, merged, {".scoped"}, {".ad-slot", "#new-banner"});
  assert(css == ".scoped { display:none !important; }\n"
                "#ad-banner,.late-ad { display:none !important; }\n");
  auto suppressed = HideStyles({".scoped"}, {});
  const auto scoped = suppressed;
  AppendSimpleGenericStyles(suppressed, true, merged, {".scoped"}, {});
  assert(suppressed == scoped);
  std::string dangerous;
  AppendSimpleGenericStyles(dangerous, false, {"body", ".x:not(.y)", ".x,.y", "#x{color:red}"}, {}, {});
  assert(dangerous.empty());

  std::vector<std::string> long_selectors;
  for (size_t i = 0; i < 3600; ++i) {
    long_selectors.push_back(".long_" + std::to_string(i) + std::string(54,'x'));
  }
  std::string bounded;
  AppendSimpleGenericStyles(bounded, false, long_selectors, {}, {});
  assert(bounded.size() <= kGenericStylesByteLimit && bounded.size() > 65'000);
  assert(bounded.ends_with("; }\n") && bounded.find(".long_3599") == bounded.npos);
  std::string tight(256 * 1024 - 40,' ');
  AppendSimpleGenericStyles(tight, false, merged, {}, {});
  assert(tight.size() <= 256 * 1024 && tight.ends_with("; }\n"));
  assert(keys.AddList("##.supplement000\n##.supplement001", 10) == 1);
  assert(keys.AddList("##.tooLate", 10) == 0);

  if (argc > 1) {
    std::ifstream file(argv[1], std::ios::binary);
    assert(file);
    const std::string body((std::istreambuf_iterator<char>(file)), {});
    SimpleGenericCensus census(
        kPackagedGenericCandidateLimit, kPackagedGenericCandidateLimit / 2);
    for (auto reviewed : kPackagedGenericAdSlots) {
      assert(census.Add(reviewed));
    }
    const auto added = census.AddList(body, kPackagedGenericCandidateLimit);
    // Bench uses all census keys as matches: worst case for this input,
    // not an adblock-rust match or an actual Chromium parser benchmark.
    auto fixture = census.Resolve([](const auto& classes, const auto& ids) {
      assert(classes.size() == kPackagedGenericCandidateLimit / 2);
      assert(ids.size() == kPackagedGenericCandidateLimit / 2);
      std::vector<std::string> out;
      for (const auto& token : classes) out.push_back("." + token);
      for (const auto& token : ids) out.push_back("#" + token);
      return out;
    });
    auto start = std::chrono::steady_clock::now();
    size_t bytes = 0;
    for (size_t i = 0; i < 1000; ++i) {
      std::string sample;
      AppendSimpleGenericStyles(sample, false, fixture, {}, {});
      bytes = sample.size();
    }
    auto elapsed = std::chrono::duration<double, std::micro>(
        std::chrono::steady_clock::now() - start).count();
    std::cout << "packaged-new=" << added << " packaged-total=" << fixture.size()
              << " css-bytes=" << bytes << " host-per-style-us=" << elapsed/1000
              << '\n';
    SimpleGenericCensus feeds(kSubscriptionGenericCandidateLimit);
    size_t failed_due_total_cap = 0;
    for (size_t list = 0; list < 30; ++list) {
      std::string generated;
      for (size_t key = 0; key < kSubscriptionGenericPerList + 10; ++key) {
        generated += "##.feed" + std::to_string(list) + "_slot" +
                     std::to_string(key) + "\n";
      }
      failed_due_total_cap +=
          kSubscriptionGenericPerList - feeds.AddList(generated, kSubscriptionGenericPerList);
    }
    assert(failed_due_total_cap == 30 * kSubscriptionGenericPerList -
                                        kSubscriptionGenericCandidateLimit);
    auto all_feeds = feeds.Resolve([](const auto& classes, const auto& ids) {
      assert(ids.empty());
      std::vector<std::string> out;
      for (const auto& token : classes) out.push_back("." + token);
      return out;
    });
    auto all = MergeSimpleGeneric(std::move(fixture), std::move(all_feeds));
    start = std::chrono::steady_clock::now();
    for (size_t i = 0; i < 1000; ++i) {
      std::string sample;
      AppendSimpleGenericStyles(sample, false, all, {}, {});
      bytes = sample.size();
    }
    elapsed = std::chrono::duration<double, std::micro>(
        std::chrono::steady_clock::now() - start).count();
    std::cout << "synthetic-thirty-feeds total-keys=" << all.size()
              << " css-bytes=" << bytes << " host-per-style-us=" << elapsed/1000
              << '\n';
  }
  std::cout << "PASS safe simple generic selector census, engine authority, "
               "cross-list exceptions, generichide, deterministic bounds\n";
}
