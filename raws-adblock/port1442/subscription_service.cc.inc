// SPDX-License-Identifier: MPL-2.0
namespace sandium::port1442 {

UrlSubscriptions::UrlSubscriptions(Profile* profile)
    : factory_(profile->GetDefaultStoragePartition()
                   ->GetURLLoaderFactoryForBrowserProcess()),
      cache_(base::ThreadPool::CreateSequencedTaskRunner(
                 {base::MayBlock(), base::TaskPriority::USER_VISIBLE}),
             profile->GetPath().AppendASCII("RawS-1442-filter-cache")) {
  cache_.AsyncCall(&ListCache::Read)
      .Then(base::BindOnce(&UrlSubscriptions::Start, weak_.GetWeakPtr()));
}

UrlSubscriptions::~UrlSubscriptions() = default;

}  // namespace sandium::port1442
