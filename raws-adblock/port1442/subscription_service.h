// SPDX-License-Identifier: MPL-2.0
// Browser-process service. No content-layer API accepts a list URL or rule payload.
// Cache writes and full-list reads run off the UI sequence. No extension runtime.
#ifndef COMPONENTS_SANDIUM_ADBLOCK_SUBSCRIPTION_SERVICE_H_
#define COMPONENTS_SANDIUM_ADBLOCK_SUBSCRIPTION_SERVICE_H_
#include <algorithm>
#include <array>
#include <cstdint>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <string>
#include <string_view>
#include <vector>
#include "base/files/file_util.h"
#include "base/files/important_file_writer.h"
#include "base/functional/bind.h"
#include "base/json/json_reader.h"
#include "base/json/json_writer.h"
#include "base/logging.h"
#include "base/memory/weak_ptr.h"
#include "base/strings/string_util.h"
#include "base/supports_user_data.h"
#include "base/task/thread_pool.h"
#include "base/threading/sequence_bound.h"
#include "base/timer/timer.h"
#include "chrome/browser/profiles/profile.h"
#include "chrome/browser/raws/catalog_generated.h"
#include "components/sandium_adblock/document_subresource_factory.h"
#include "chrome/browser/raws/subscription_policy.h"
#include "content/public/browser/storage_partition.h"
#include "net/base/net_errors.h"
#include "net/url_request/redirect_info.h"
#include "net/traffic_annotation/network_traffic_annotation.h"
#include "services/network/public/cpp/resource_request.h"
#include "services/network/public/cpp/shared_url_loader_factory.h"
#include "services/network/public/cpp/simple_url_loader.h"
#include "services/network/public/mojom/fetch_api.mojom.h"
#include "url/origin.h"
namespace sandium::port1442 {
inline constexpr size_t kListLimit = network::SimpleURLLoader::kMaxBoundedStringDownloadSize, kAllLimit = 96u << 20;
using Flags = std::array<Subscription, std::size(kCatalog)>;
struct Startup { bool valid=true; Flags flags{}; std::vector<size_t> missing; std::vector<std::string> bodies; };
// The filenames are SHA-256 of the full catalogue URL, not indexes or user input.
class ListCache {
 public:
  explicit ListCache(base::FilePath dir) : dir_(std::move(dir)) {}
  Startup Read() {
    Startup out;
    std::string state;
    std::optional<base::DictValue> data;
    if (base::PathExists(dir_.AppendASCII("state.json"))) {
      if (base::ReadFileToStringWithMaxSize(dir_.AppendASCII("state.json"), &state, 256*1024))
        data = base::JSONReader::ReadDict(state, base::JSON_PARSE_RFC);
      // Do not resurrect disabled or deleted subscriptions after state corruption.
      if (!data) { for (auto& v : out.flags) v.enabled = false; return out; }
    }
    size_t budget = kAllLimit;
    for (size_t i = 0; i < out.flags.size(); ++i) {
      auto& f = out.flags[i];
      if (const auto* d = data ? data->FindDict(kCatalog[i].url) : nullptr) {
        f.enabled = d->FindBool("enabled").value_or(false);
        f.deleted = d->FindBool("deleted").value_or(false);
        f.expires_hours = std::clamp(d->FindInt("expires").value_or(kDefaultHours), 0, kMaxHours);
        f.attempt = static_cast<int64_t>(std::clamp(d->FindDouble("attempt").value_or(0.0),0.0,253402300799.0));
        f.success = static_cast<int64_t>(std::clamp(d->FindDouble("success").value_or(0.0),0.0,253402300799.0));
      }
      if (!f.Available()) continue;
      std::string body;
      if (!base::ReadFileToStringWithMaxSize(dir_.AppendASCII(kCatalog[i].key), &body, kListLimit) ||
          !Accept(body)) { out.missing.push_back(i); continue; }
      // Never install an arbitrary prefix of an oversized multi-list generation.
      if (body.size() > budget) { LOG(WARNING) << "RawS filter snapshot exceeds byte limit; retaining active rules"; out.valid=false;out.bodies.clear(); return out; }
      budget -= body.size(); out.bodies.push_back(std::move(body));
    }
    return out;
  }
  static bool Accept(const std::string& s) {
    const std::string_view view(s);
    const auto text = view.starts_with("\xEF\xBB\xBF") ? view.substr(3) : view;
    const auto first = text.find_first_not_of(" \t\r\n");
    return first != text.npos && text[first] != '<' && s.size() <= kListLimit &&
           s.find('\0') == s.npos && base::IsStringUTF8(s);
  }
  int Store(size_t i, std::string body) {
    if (!Accept(body))
      return -1;
    const auto expiry = adblock_native::InspectSubscription(body);
    // A response with no parsed rules must never replace the last good file.
    if (!expiry || !base::CreateDirectory(dir_) ||
        !base::ImportantFileWriter::WriteFileAtomically(dir_.AppendASCII(kCatalog[i].key), body))
      return -1;
    return *expiry;
  }
  void Save(Flags flags) {
    base::DictValue all;
    for (size_t i = 0; i < flags.size(); ++i) {
      const auto& f = flags[i]; base::DictValue v;
      v.Set("enabled", f.enabled); v.Set("deleted", f.deleted); v.Set("expires", f.expires_hours);
      v.Set("attempt", static_cast<double>(f.attempt)); v.Set("success", static_cast<double>(f.success));
      all.Set(kCatalog[i].url, std::move(v));
    }
    if (auto s = base::WriteJson(all); s && base::CreateDirectory(dir_))
      base::ImportantFileWriter::WriteFileAtomically(dir_.AppendASCII("state.json"), *s);
  }
 private:
  base::FilePath dir_;
};
class UrlSubscriptions final : public base::SupportsUserData::Data {
 public:
  explicit UrlSubscriptions(Profile* profile)
      : factory_(profile->GetDefaultStoragePartition()->GetURLLoaderFactoryForBrowserProcess()),
        cache_(base::ThreadPool::CreateSequencedTaskRunner({base::MayBlock(), base::TaskPriority::USER_VISIBLE}),
               profile->GetPath().AppendASCII("RawS-1442-filter-cache")) {
    cache_.AsyncCall(&ListCache::Read).Then(base::BindOnce(&UrlSubscriptions::Start, weak_.GetWeakPtr()));
  }
  // Native control surface for the existing host; no UI, JNI, or extension is added.
  // Tombstones are persistent. Background replies never install a disabled list.
  void SetChoice(size_t i,bool enabled,bool deleted) {
    if (!started_ || i>=flags_.size()) return;
    flags_[i].enabled=enabled;flags_[i].deleted=deleted; ++generation_;
    queue_.erase(i);cache_.AsyncCall(&ListCache::Save).WithArgs(flags_);
    if (flags_[i].Available()) Queue(i);
    dirty_=true;Pump();
  }
  void Refresh(bool manual) {
    if (!started_) return;
    for (size_t i=0;i<flags_.size();++i)
      if (flags_[i].Due(Now(), false, manual)) Queue(i);
    Pump();
  }
 private:
  static int64_t Now() { return base::Time::Now().InMillisecondsSinceUnixEpoch() / 1000; }
  void Start(Startup out) {
    flags_=out.flags; started_=true;
    if (!out.bodies.empty()) adblock_native::InstallAdditionalRules(std::move(out.bodies));
    for (auto i:out.missing) Queue(i);
    Pump();
    initial_.Start(FROM_HERE,base::Seconds(kInitialSeconds),base::BindOnce(&UrlSubscriptions::OnInitial,weak_.GetWeakPtr()));
  }
  void OnInitial() {
    Refresh(false);
    timer_.Start(FROM_HERE,base::Seconds(kTickSeconds),base::BindRepeating(&UrlSubscriptions::Refresh,weak_.GetWeakPtr(),false));
  }
  void Queue(size_t i) { if(flags_[i].Available() && !busy_.contains(i)) queue_.insert(i); }
  void Pump() {
    while (busy_.size()<3 && !queue_.empty()) {
      size_t i=*queue_.begin();queue_.erase(i);
      if (!flags_[i].Available()) continue;
      busy_.insert(i);
      auto req=std::make_unique<network::ResourceRequest>();req->url=GURL(kCatalog[i].url);
      req->credentials_mode=network::mojom::CredentialsMode::kOmit;
      req->redirect_mode=network::mojom::RedirectMode::kFollow;
      auto tag=net::DefineNetworkTrafficAnnotation("raws_curated_filter_download", R"(
        semantics { sender: "RawS content blocker" description: "Refresh enabled content filter rules." trigger: "Profile startup, expiry or explicit refresh." data: "HTTPS request for the public list, without page URLs or cookies." destination: OTHER }
        policy { cookies_allowed: NO setting: "Enabled URL subscriptions" policy_exception_justification: "This experimental browser does not expose an enterprise policy." })");
      auto load=network::SimpleURLLoader::Create(std::move(req),tag);
      load->SetOnRedirectCallback(base::BindRepeating(&UrlSubscriptions::Redirect,weak_.GetWeakPtr(),i));
      load->SetTimeoutDuration(base::Seconds(45));
      auto* ptr=load.get();loads_[i]=std::move(load);
      ptr->DownloadToString(factory_.get(),base::BindOnce(&UrlSubscriptions::Got,weak_.GetWeakPtr(),i),kListLimit);
    }
    if (busy_.empty() && dirty_) {
      dirty_=false;
      cache_.AsyncCall(&ListCache::Read).Then(base::BindOnce(&UrlSubscriptions::Reload,weak_.GetWeakPtr(),generation_));
    }
  }
  void Reload(uint64_t generation,Startup out) {
    if (generation == generation_ && out.valid) adblock_native::InstallAdditionalRules(std::move(out.bodies));
  }
  void Redirect(size_t i,const GURL&,const net::RedirectInfo& info,
                const network::mojom::URLResponseHead&,std::vector<std::string>*) {
    const GURL& u=info.new_url;
    // The catalog authorizes only the originally configured origin; do not
    // send even credential-free requests to arbitrary third parties or ports.
    const url::Origin source = url::Origin::Create(GURL(kCatalog[i].url));
    if (!u.SchemeIs("https") || u.has_username() || u.has_password() ||
        url::Origin::Create(u) != source) {
      loads_.erase(i);flags_[i].attempt=Now();End(i,false,kDefaultHours);
    }
  }
  void Got(size_t i,std::optional<std::string> body) {
    bool ok=loads_.at(i)->NetError()==net::OK && flags_[i].Available() && body && !body->empty();
    loads_.erase(i);flags_[i].attempt=Now();
    if (!ok) { End(i,false,kDefaultHours); return; }
    cache_.AsyncCall(&ListCache::Store).WithArgs(i,std::move(*body)).Then(
        base::BindOnce(&UrlSubscriptions::Stored,weak_.GetWeakPtr(),i));
  }
  void Stored(size_t i,int hours) { End(i,hours>=0,hours); }
  void End(size_t i,bool ok,int hours) {
    if(ok){flags_[i].success=flags_[i].attempt;flags_[i].expires_hours=hours;dirty_=true;}
    else { LOG(WARNING) << "RawS filter download/cache failure for catalogue entry " << i;
      if(flags_[i].success==flags_[i].attempt) --flags_[i].success; }
    cache_.AsyncCall(&ListCache::Save).WithArgs(flags_);busy_.erase(i);Pump();
  }
  scoped_refptr<network::SharedURLLoaderFactory> factory_;
  base::SequenceBound<ListCache> cache_;
  Flags flags_{};std::set<size_t> queue_,busy_;
  std::map<size_t,std::unique_ptr<network::SimpleURLLoader>> loads_;
  base::OneShotTimer initial_;base::RepeatingTimer timer_;
  uint64_t generation_=0;
  bool started_=false,dirty_=false;
  base::WeakPtrFactory<UrlSubscriptions> weak_{this};
};
inline constexpr char kSubscriptionServiceKey[]="raws-1442-filter-service";
inline UrlSubscriptions* GetSubscriptions(Profile* profile) {
  if (!profile || profile->IsOffTheRecord()) return nullptr;
  return static_cast<UrlSubscriptions*>(profile->GetUserData(kSubscriptionServiceKey));
}
inline void StartSubscriptions(Profile* profile) {
  if (!profile || profile->IsOffTheRecord() || GetSubscriptions(profile)) return;
  profile->SetUserData(kSubscriptionServiceKey,std::make_unique<UrlSubscriptions>(profile));
}
}  // namespace sandium::port1442
#endif
