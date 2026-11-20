// Start-up-only buffer on the browser UI sequence. Normal navigation and
// network loading do not call it or wait for it. As in the warm path, the
// reply is scoped to the original WeakDocumentPtr at the call site.
class CosmeticReadinessQueue {
 public:
  CosmeticReadinessQueue();
  ~CosmeticReadinessQueue();

  void Push(base::TimeTicks now, base::OnceClosure query) {
    if (queries_.size() < 8) {
      queries_.emplace_back(now, std::move(query));
    }
  }
  void Finish(bool ready, base::TimeTicks now) {
    auto queries = std::move(queries_);
    queries_.clear();
    if (!ready) {
      return;
    }
    for (auto& [queued_at, query] : queries) {
      if (now - queued_at < base::Seconds(5)) {
        std::move(query).Run();
      }
    }
  }
 private:
  std::vector<std::pair<base::TimeTicks, base::OnceClosure>> queries_;
};

CosmeticReadinessQueue::CosmeticReadinessQueue() = default;
CosmeticReadinessQueue::~CosmeticReadinessQueue() = default;
