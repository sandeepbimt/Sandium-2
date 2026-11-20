// SPDX-License-Identifier: MPL-2.0
// Exercises the actual coordinator with fake workers; not Chromium compilation.
#include <cassert>
#include <cstdint>
#include <functional>
#include <iostream>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "cosmetic_host_clock.h"
#include "cosmetic_readiness.cc.inc"

#define LOG(level) std::cerr
using Bodies = std::vector<std::string>;
class RuleSnapshot {
 public:
  bool Initialize(std::string, Bodies, bool) { return true; }
};
namespace base {
enum class TaskPriority { USER_VISIBLE };
struct ThreadPool {
  static int CreateSequencedTaskRunner(TaskPriority) {
    static int last = 100;
    return ++last;
  }
};
std::function<void(bool)> BindOnce(void (*callback)(uint64_t, bool), uint64_t revision) {
  return [callback, revision](bool ok) { callback(revision, ok); };
}
struct Job {
  int sequence;
  Bodies options;
  std::function<void(bool)> reply;
};
std::vector<Job>& Jobs() { static std::vector<Job> jobs; return jobs; }
template<class Snapshot>
struct SequenceBound {
  SequenceBound()=default;
  explicit SequenceBound(int runner): id(runner) {}
  SequenceBound(SequenceBound&& other) noexcept : id(std::exchange(other.id,0)) {}
  SequenceBound& operator=(SequenceBound&& other) noexcept {
    id=std::exchange(other.id,0); return *this;
  }
  void Reset() { id=0; }
  struct Builder {
    SequenceBound& owner;
    Bodies bodies;
    Builder& WithArgs(const std::string& packaged, Bodies incoming, bool initialize_resolver) {
      assert(packaged=="packaged" && !initialize_resolver);bodies=std::move(incoming);return *this;
    }
    void Then(std::function<void(bool)> reply) {
      Jobs().push_back({owner.id,std::move(bodies),std::move(reply)});
    }
  };
  Builder AsyncCall(bool (Snapshot::*)(std::string, Bodies, bool)) { return {*this,{}}; }
  int id=0;
};
}  // namespace base
struct State {
  base::SequenceBound<RuleSnapshot> snapshot{1};
  bool attempted=true;
  bool failed=false;
  CosmeticReadinessQueue cosmetic_waiters;
  bool ready=false;
  std::string packaged_rules="packaged";
  std::optional<Bodies> queued_refresh;
  uint64_t refresh_revision=0;
  bool refresh_in_flight=false;
  base::SequenceBound<RuleSnapshot> refresh_candidate;
};
State& GetState() { static State state; return state; }

#include "refresh.cc.inc"
#include "refresh_submit_actual.inc"

int main() {
  auto& state=GetState();
  InstallAdditionalRules({"old"});
  InstallAdditionalRules({"queued-before-ready"});
  assert(base::Jobs().empty() && state.snapshot.id==1);
  int cosmetic_replays=0;
  state.cosmetic_waiters.Push(base::TimeTicks::Now(),
      base::OnceClosure([&] {
        assert(state.ready && !state.failed);
        ++cosmetic_replays;
      }));
  OnInitialized(true);
  assert(cosmetic_replays==1);
  assert(base::Jobs().size()==1 && base::Jobs()[0].options==Bodies{"queued-before-ready"});
  assert(base::Jobs()[0].sequence!=state.snapshot.id && state.snapshot.id==1);
  InstallAdditionalRules({"superseded"});
  InstallAdditionalRules({"latest"});
  assert(base::Jobs().size()==1 && state.snapshot.id==1);
  auto first_reply=std::move(base::Jobs()[0].reply);
  first_reply(true);
  assert(base::Jobs().size()==2 && state.snapshot.id==1);
  assert(base::Jobs()[1].options==Bodies{"latest"});
  int replacement=base::Jobs()[1].sequence;
  auto second_reply=std::move(base::Jobs()[1].reply);
  second_reply(true);
  assert(state.snapshot.id==replacement && !state.refresh_in_flight);
  InstallAdditionalRules({"failed"});
  auto bad_reply=std::move(base::Jobs().back().reply);
  bad_reply(false);
  assert(state.snapshot.id==replacement && !state.refresh_in_flight);
  state.ready=false;
  InstallAdditionalRules({"queued-before-failure"});
  state.cosmetic_waiters.Push(base::TimeTicks::Now(),
      base::OnceClosure([&] { ++cosmetic_replays; }));
  OnInitialized(false);
  assert(cosmetic_replays==1);
  assert(state.failed && !state.ready && !state.queued_refresh);
  std::cout << "PASS prewarm, separate runners, coalescing, stale/failed retention\n";
}
