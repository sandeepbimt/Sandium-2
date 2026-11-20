void StartQueuedRefresh();

void OnRefreshBuilt(uint64_t revision, bool ok) {
  auto& state = GetState();
  if (ok && revision == state.refresh_revision) {
    // Move the holder, not the engine or any of its sequence-affine Rust
    // handles. Previously posted decisions finish on the former sequence.
    state.snapshot = std::move(state.refresh_candidate);
  } else {
    state.refresh_candidate.Reset();
    if (!ok)
      LOG(WARNING) << "RawS additional rules rejected; retaining previous snapshot";
  }
  state.refresh_in_flight = false;
  StartQueuedRefresh();
}

void StartQueuedRefresh() {
  auto& state = GetState();
  if (!state.ready || state.refresh_in_flight || !state.queued_refresh)
    return;
  // At most one refresh in flight and one coalesced pending generation. Matching
  // uses the last valid complete snapshot throughout rebuild, on its own queue.
  auto bodies = std::move(*state.queued_refresh);
  state.queued_refresh.reset();
  state.refresh_in_flight = true;
  state.refresh_candidate = base::SequenceBound<RuleSnapshot>(
      base::ThreadPool::CreateSequencedTaskRunner({base::TaskPriority::USER_VISIBLE}));
  state.refresh_candidate.AsyncCall(&RuleSnapshot::Initialize)
      .WithArgs(state.packaged_rules, std::move(bodies), false)
      .Then(base::BindOnce(&OnRefreshBuilt, state.refresh_revision));
}

void OnInitialized(bool ready) {
  auto& state = GetState();
  state.failed = !ready;
  state.ready = ready;
  state.cosmetic_waiters.Finish(ready, base::TimeTicks::Now());
  if (!ready) {
    state.queued_refresh.reset();
    state.packaged_rules.clear();
    return;
  }
  StartQueuedRefresh();
}
