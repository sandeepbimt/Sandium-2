bool OfflineRulesReady() { return GetState().ready; }
std::optional<int> InspectSubscription(const std::string& text) {
  const auto first = text.find_first_not_of(" \t\r\n");
  if (first == text.npos || text.size() > kMaxRulesBytes ||
      text.find('\0') != text.npos || !base::IsStringUTF8(text))
    return std::nullopt;
  DATFileDataBuffer bytes(text.begin(), text.end());
  // Metadata comes from original bytes; match admission reflects the same
  // in-memory preprocessing and permission mask as the active rule engine.
  const auto meta = adblock::read_list_metadata(bytes);
  PruneSandiumSubscription(bytes);
  auto filters = adblock::new_filter_set(false);
  if (filters->add_filter_list_with_permissions(bytes, 0).result_kind !=
      adblock::ResultKind::Success)
    return std::nullopt;
  auto parsed = adblock::engine_from_filter_set(std::move(filters));
  if (parsed.result_kind != adblock::ResultKind::Success)
    return std::nullopt;
  // The pinned add_filter_list result is only ingestion metadata. Actual
  // parser counts are exposed on the compiled engine, even with debug=false.
  const auto report = parsed.value->get_debug_info();
  if (report.source_info.size() != 1)
    return std::nullopt;
  const auto& feed = report.source_info[0];
  if (feed.network_filter_count == 0 && feed.cosmetic_filter_count == 0)
    return std::nullopt;
  return meta.expires_hours.has_value && meta.expires_hours.value <= 336
             ? meta.expires_hours.value
             : 168;
}
void InstallAdditionalRules(std::vector<std::string> bodies) {
  auto& s=GetState(); if (!s.attempted || s.failed) return;
  ++s.refresh_revision;
  s.queued_refresh = std::move(bodies);
  StartQueuedRefresh();
}
void QueryPopup(GURL target,GURL frame,base::OnceCallback<void(bool)> reply) {
  auto& s=GetState();
  if (!s.ready || s.pending>=kMaxPendingChecks) {
    // Always deliver asynchronously: a throttle must have returned DEFER first.
    base::SequencedTaskRunner::GetCurrentDefault()->PostTask(FROM_HERE,base::BindOnce(std::move(reply),false));return;
  }
  ++s.pending;
  s.snapshot.AsyncCall(&RuleSnapshot::Popup).WithArgs(std::move(target),std::move(frame)).Then(
     base::BindOnce([](base::OnceCallback<void(bool)> cb,bool block){--GetState().pending;std::move(cb).Run(block);},std::move(reply)));
}
void QueryHideStyles(GURL url,base::OnceCallback<void(std::string)> reply) {
  auto& s=GetState();
  if (!s.ready) {
    if (s.attempted && !s.failed && url.spec().size() <= 16 * 1024)
      s.cosmetic_waiters.Push(base::TimeTicks::Now(),
          base::BindOnce(&QueryHideStyles, std::move(url), std::move(reply)));
    return;
  }
  if (s.pending>=kMaxPendingChecks) return;
  ++s.pending;
  s.snapshot.AsyncCall(&RuleSnapshot::Style).WithArgs(std::move(url)).Then(
     base::BindOnce([](base::OnceCallback<void(std::string)> cb,std::string css){--GetState().pending;std::move(cb).Run(std::move(css));},std::move(reply)));
}
bool CheckSubframe(GURL target,const url::Origin& initiator,base::OnceCallback<void(bool)> reply) {
  auto& s=GetState();if(!s.ready || s.pending>=kMaxPendingChecks) return false;
  ++s.pending;s.snapshot.AsyncCall(&RuleSnapshot::Evaluate).WithArgs(std::move(target),Resource::kSubFrame,initiator,std::string("GET")).Then(
    base::BindOnce([](base::OnceCallback<void(bool)> cb,Action result){--GetState().pending;std::move(cb).Run(result==Action::kBlock);},std::move(reply)));
  return true;
}
