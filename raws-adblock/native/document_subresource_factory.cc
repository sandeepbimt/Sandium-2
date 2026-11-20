// SPDX-License-Identifier: MPL-2.0
#include "components/sandium_adblock/document_subresource_factory.h"

#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <utility>
#include <vector>

#include "base/check.h"
#include "base/containers/flat_map.h"
#include "base/functional/bind.h"
#include "base/location.h"
#include "base/memory/weak_ptr.h"
#include "base/no_destructor.h"
#include "base/sequence_checker.h"
#include "base/strings/string_util.h"
#include "base/task/thread_pool.h"
#include "base/threading/sequence_bound.h"
#include "base/timer/timer.h"
#include "components/sandium_adblock/subresource_decision.h"
#include "mojo/public/cpp/bindings/remote.h"
#include "mojo/public/cpp/bindings/self_owned_receiver.h"
#include "net/base/net_errors.h"
#include "services/network/public/cpp/resource_request.h"
#include "services/network/public/cpp/url_loader_completion_status.h"
#include "services/network/public/cpp/url_loader_factory_builder.h"
#include "services/network/public/mojom/url_loader.mojom.h"
#include "services/network/public/mojom/url_loader_factory.mojom.h"

namespace sandium::adblock_native {
namespace {

constexpr std::size_t kMaxRulesBytes = 8 * 1024 * 1024;
constexpr int kMaxPendingChecks = 32;
constexpr auto kCheckTimeout = base::Milliseconds(50);
using Resource = blink::mojom::ResourceType;
using Action = SubresourceAction;

class RuleSnapshot {
 public:
  bool Initialize(std::string text) {
    if (!base::IsStringUTF8(text) ||
        text.find('\0') != std::string::npos ||
        !adblock::set_domain_resolver()) {
      return false;
    }
    auto primary = adblock::new_filter_set(false);
    const std::vector<uint8_t> bytes(text.begin(), text.end());
    const auto admitted = primary->add_filter_list(bytes);
    if (admitted.result_kind != adblock::ResultKind::Success) return false;
    auto primary_engine = adblock::engine_from_filter_set(std::move(primary));
    if (primary_engine.result_kind != adblock::ResultKind::Success) {
      return false;
    }
    primary_.emplace(std::move(primary_engine.value));
    additional_.emplace(adblock::new_engine());
    return true;
  }

  Action Evaluate(GURL url, Resource type, url::Origin initiator,
                  std::string method) {
    if (!primary_ || !additional_) return Action::kNotEvaluated;
    return DecideDocumentSubresource(&**primary_, &**additional_, url, type,
                                     initiator, method);
  }

 private:
  std::optional<rust::Box<adblock::Engine>> primary_;
  std::optional<rust::Box<adblock::Engine>> additional_;
};

// UI-sequence owned. There is no mutable renderer- or profile-controlled state.
// The bounded worker never receives a Mojo endpoint or a raw frame pointer.
struct State {
  base::SequenceBound<RuleSnapshot> snapshot;
  SEQUENCE_CHECKER(sequence_checker);
  bool attempted = false;
  bool failed = false;
  int pending = 0;
};

State& GetState() {
  static base::NoDestructor<State> state;
  DCHECK_CALLED_ON_VALID_SEQUENCE(state->sequence_checker);
  return *state;
}

std::optional<Resource> GetResourceType(int type) {
  for (auto allowed : {Resource::kScript, Resource::kStylesheet, Resource::kImage,
                       Resource::kFontResource}) {
    if (type == static_cast<int>(allowed)) return allowed;
  }
  return std::nullopt;
}

class RequestFactory final : public network::mojom::URLLoaderFactory {
 public:
  RequestFactory(mojo::PendingRemote<network::mojom::URLLoaderFactory> downstream,
                 const url::Origin& document_origin)
      : downstream_(std::move(downstream)), document_origin_(document_origin) {}

  ~RequestFactory() override = default;

  void CreateLoaderAndStart(
      mojo::PendingReceiver<network::mojom::URLLoader> loader,
      int32_t request_id, uint32_t options,
      const network::ResourceRequest& request,
      mojo::PendingRemote<network::mojom::URLLoaderClient> client,
      const net::MutableNetworkTrafficAnnotationTag& annotation) override {
    auto& state = GetState();
    const auto type = GetResourceType(request.resource_type);
    if (!state.attempted || state.failed || state.pending >= kMaxPendingChecks || !type ||
        request.trusted_params || request.request_body ||
        !request.request_initiator ||
        *request.request_initiator != document_origin_ ||
        !request.url.SchemeIsHTTPOrHTTPS() || request.url.spec().size() > 65536 ||
        (request.method != "GET" && request.method != "HEAD")) {
      downstream_->CreateLoaderAndStart(std::move(loader), request_id, options,
                                        request, std::move(client), annotation);
      return;
    }
    const uint64_t token = ++next_token_;
    auto pending = std::make_unique<Pending>();
    pending->complete = base::BindOnce(&RequestFactory::Finish,
        weak_factory_.GetWeakPtr(), std::move(loader), request_id, options,
        request, std::move(client), annotation);
    pending->timer.Start(FROM_HERE, kCheckTimeout,
                         base::BindOnce(&RequestFactory::Complete,
                             weak_factory_.GetWeakPtr(), token, Action::kAllow));
    pending_[token] = std::move(pending);
    ++state.pending;
    state.snapshot.AsyncCall(&RuleSnapshot::Evaluate)
        .WithArgs(request.url, *type, document_origin_, request.method)
        .Then(base::BindOnce(&RequestFactory::OnEvaluated,
                             weak_factory_.GetWeakPtr(), token));
  }

  void Clone(mojo::PendingReceiver<network::mojom::URLLoaderFactory> receiver)
      override {
    mojo::PendingRemote<network::mojom::URLLoaderFactory> clone;
    downstream_->Clone(clone.InitWithNewPipeAndPassReceiver());
    mojo::MakeSelfOwnedReceiver(
        std::make_unique<RequestFactory>(std::move(clone), document_origin_),
        std::move(receiver));
  }

 private:
  struct Pending {
    base::OneShotTimer timer;
    base::OnceCallback<void(Action)> complete;
  };

  // Global budget is released on worker reply, not timeout, so an engine
  // stalled by one task cannot accumulate new work indefinitely. This static
  // callback does not depend on the factory remaining alive.
  static void OnEvaluated(base::WeakPtr<RequestFactory> factory,
                          uint64_t token, Action action) {
    --GetState().pending;
    if (factory) factory->Complete(token, action);
  }

  void Complete(uint64_t token, Action action) {
    auto it = pending_.find(token);
    if (it == pending_.end()) return;
    auto complete = std::move(it->second->complete);
    pending_.erase(it);
    std::move(complete).Run(action);
  }

  void Finish(
      mojo::PendingReceiver<network::mojom::URLLoader> loader,
      int32_t request_id, uint32_t options,
      const network::ResourceRequest& request,
      mojo::PendingRemote<network::mojom::URLLoaderClient> client,
      const net::MutableNetworkTrafficAnnotationTag& annotation, Action action) {
    if (action == Action::kBlock) {
      mojo::Remote<network::mojom::URLLoaderClient> response(std::move(client));
      response->OnComplete(
          network::URLLoaderCompletionStatus(net::ERR_BLOCKED_BY_CLIENT));
      return;
    }
    // No URLLoader proxy is created: downstream Chromium exclusively validates
    // and follows redirects. No flags or request details are mutated.
    downstream_->CreateLoaderAndStart(std::move(loader), request_id, options,
                                      request, std::move(client), annotation);
  }

  mojo::Remote<network::mojom::URLLoaderFactory> downstream_;
  const url::Origin document_origin_;
  uint64_t next_token_ = 0;
  base::flat_map<uint64_t, std::unique_ptr<Pending>> pending_;
  base::WeakPtrFactory<RequestFactory> weak_factory_{this};
};

void OnInitialized(bool ready) { GetState().failed = !ready; }

}  // namespace

void InitializeDocumentSubresourceRules(std::string verified_rules) {
  auto& state = GetState();
  if (state.attempted || verified_rules.empty() ||
      verified_rules.size() > kMaxRulesBytes) {
    return;
  }
  state.attempted = true;
  state.snapshot = base::SequenceBound<RuleSnapshot>(
      base::ThreadPool::CreateSequencedTaskRunner({base::TaskPriority::USER_VISIBLE}));
  state.snapshot.AsyncCall(&RuleSnapshot::Initialize)
      .WithArgs(std::move(verified_rules))
      .Then(base::BindOnce(&OnInitialized));
}

void MaybeAppendDocumentSubresourceFactory(
    network::URLLoaderFactoryBuilder& builder,
    const url::Origin& document_origin) {
  const auto& state = GetState();
  if (!state.attempted || state.failed || document_origin.opaque() ||
      (document_origin.scheme() != "http" && document_origin.scheme() != "https")) {
    return;
  }
  auto [receiver, downstream] = builder.Append();
  mojo::MakeSelfOwnedReceiver(
      std::make_unique<RequestFactory>(std::move(downstream), document_origin),
      std::move(receiver));
}

}  // namespace sandium::adblock_native
