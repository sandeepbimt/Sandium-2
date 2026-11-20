// SPDX-License-Identifier: MPL-2.0
#include <cassert>
#include <functional>
#include <utility>
#include <vector>

#include "cosmetic_host_clock.h"
#include "cosmetic_readiness.cc.inc"

int main() {
  CosmeticReadinessQueue queue;
  int queries = 0;
  int hands_off = 0;
  auto push = [&](int at) {
    queue.Push(base::TimeTicks(at),
               base::OnceClosure([&] { ++queries; }));
  };
  push(0);
  assert(queries == 0);
  queue.Finish(false, base::TimeTicks(1));
  queue.Finish(true, base::TimeTicks(2));
  assert(queries == 0);

  push(5);  // Five seconds at readiness: expires.
  push(6);  // Less than five seconds: replay exactly once.
  queue.Finish(true, base::TimeTicks(10));
  queue.Finish(true, base::TimeTicks(11));
  assert(queries == 1);

  for (int i = 0; i < 12; ++i) push(12);
  queue.Finish(true, base::TimeTicks(13));
  assert(queries == 9);

  // The readiness gate does not replace the existing document-identity gate.
  int doc_generation = 1;
  auto retry = [&](int expected) {
    return base::OnceClosure([&, expected] {
      ++queries;
      if (expected == doc_generation) ++hands_off;
    });
  };
  queue.Push(base::TimeTicks(14), retry(doc_generation));
  ++doc_generation;  // A different document, even at the same URL.
  queue.Push(base::TimeTicks(14), retry(doc_generation));
  queue.Finish(true, base::TimeTicks(15));
  assert(queries == 11);
  assert(hands_off == 1);
}
