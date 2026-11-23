struct NativeLoader : network::mojom::URLLoader {
  unsigned follows=0;
  std::string override_target;
  int original_headers=0;
  void FollowRedirect(network::HttpRequestHeadersUpdateParams h,
                      const std::optional<GURL>& url) override {
    follows++;original_headers=h.sentinel;override_target=url?url->text:"";
  }
  void SetPriority(net::RequestPriority,int32_t) override {}
};
struct RendererClient : network::mojom::URLLoaderClient {
  int error=0,redirected=0,completed=0;
  bool collapse=false;
  void OnReceiveEarlyHints(network::mojom::EarlyHintsPtr)override{}
  void OnReceiveResponse(network::mojom::URLResponseHeadPtr,
      mojo::ScopedDataPipeConsumerHandle,std::optional<mojo_base::BigBuffer>)override{}
  void OnReceiveRedirect(const net::RedirectInfo&,network::mojom::URLResponseHeadPtr)override{redirected++;}
  void OnUploadProgress(int64_t,int64_t,OnUploadProgressCallback)override{}
  void OnTransferSizeUpdated(int32_t)override{}
  void OnComplete(const network::URLLoaderCompletionStatus& s)override{
    error=s.error_code;collapse=s.should_collapse_initiator;completed++;
  }
};
int main() {
  auto& s=GetState(); NativeLoader down; RendererClient up;
  bool gate=true, closed=false;int blocks=0;
  {
    ScopedRedirectHop p({&up,{{&closed}}},Resource::kImage,{},
                        [&]{return gate;},{},[&]{blocks++;});
    p.downstream_.ptr=&down;
    p.OnReceiveRedirect({{"https://ad.test/blocked"},"GET"},{});
    assert(up.redirected==1);
    p.FollowRedirect({17},std::nullopt);
    assert(s.pending==1&&down.follows==0);
    s.Reply(Action::kBlock);
    assert(s.pending==0&&down.follows==0&&up.completed==1&&
           up.error==net::ERR_BLOCKED_BY_CLIENT&&up.collapse&&blocks==1);
  }
  {
    ScopedRedirectHop p({&up,{{&closed}}},Resource::kScript,{},
                        [&]{return gate;},{},[&]{blocks++;});
    p.downstream_.ptr=&down;
    p.OnReceiveRedirect({{"https://same.test/a"},"GET"},{});
    p.FollowRedirect({21},GURL{"https://same.test/choice"});
    assert(s.targets.back()=="https://same.test/choice");
    s.Reply(Action::kAllow);
    assert(down.follows==1&&down.original_headers==21&&
           down.override_target=="https://same.test/choice");
    p.OnReceiveRedirect({{"https://same.test/other"},"HEAD"},{});
    p.FollowRedirect({31},GURL{"https://cross.test/choice"});
    assert(down.follows==2&&down.original_headers==31&&s.pending==0);
    p.OnReceiveRedirect({{"https://same.test/other"},"HEAD"},{});
    p.FollowRedirect({41},std::nullopt);
    gate=false;
    s.Reply(Action::kBlock);
    assert(down.follows==3&&down.original_headers==41&&blocks==1);
  }
  gate=true;
  {
    ScopedRedirectHop p({&up,{{&closed}}},Resource::kScript,{},
                        [&]{return gate;},{},[&]{blocks++;});
    p.downstream_.ptr=&down;
    p.OnReceiveRedirect({{"https://same.test/a"},"GET"},{});
    p.FollowRedirect({51},std::nullopt);
    assert(down.follows==3&&s.pending==1&&p.timer_.budget.n==50);
    base::clock+=50;p.timer_.Fire();
    assert(down.follows==4&&s.pending==1&&p.remaining_.is_zero());
    s.Reply(Action::kBlock);
    assert(s.pending==0&&down.follows==4&&blocks==1);
    p.OnReceiveRedirect({{"https://same.test/b"},"GET"},{});
    p.FollowRedirect({61},std::nullopt);
    assert(down.follows==5&&s.pending==0);
  }
  {
    ScopedRedirectHop p({&up,{{&closed}}},Resource::kScript,{},
                        [&]{return gate;},{},[&]{blocks++;});
    p.downstream_.ptr=&down;
    p.OnReceiveRedirect({{"https://same.test/a"},"GET"},{});
    p.FollowRedirect({71},std::nullopt);
    closed=true;s.Reply(Action::kBlock);
    assert(up.error==net::ERR_BLOCKED_BY_CLIENT&&!up.collapse&&blocks==1);
  }
  closed=false;
  {
    ScopedRedirectHop p({&up,{{&closed}}},Resource::kScript,{},
                        [&]{return gate;},{},[&]{blocks++;});
    p.downstream_.ptr=&down;
    p.OnReceiveRedirect({{"https://same.test/a"},"GET"},{});
    p.FollowRedirect({81},std::nullopt);
    assert(s.pending==1);
  }
  s.Reply(Action::kBlock);
  assert(s.pending==0&&blocks==1&&down.follows==5);
  {
    base::Callback<void(bool)> custom_result;
    ScopedRedirectHop p({&up,{{&closed}}},Resource::kScript,{},
       [&]{return gate;},
       [&](GURL target,int type,url::Origin,std::string method,
           base::Callback<void(bool)> cb){
          assert(target.text=="https://same.test/a"&&type==1&&method=="GET");
          custom_result=std::move(cb);return true;},
       [&]{blocks++;});
    p.downstream_.ptr=&down;
    p.OnReceiveRedirect({{"https://same.test/a"},"GET"},{});
    p.FollowRedirect({91},std::nullopt);
    assert(s.pending==2&&down.follows==5);
    s.Reply(Action::kAllow);
    assert(s.pending==1&&down.follows==5);
    custom_result.Run(true);
    assert(s.pending==0&&blocks==2&&down.follows==5&&
           up.error==net::ERR_BLOCKED_BY_CLIENT);
  }
  {
    ScopedRedirectHop p({&up,{{&closed}}},Resource::kScript,{},
         [&]{return gate;},{},[&]{blocks++;});
    p.downstream_.ptr=&down;
    s.pending=kMaxPendingChecks;
    p.OnReceiveRedirect({{"https://same.test/a"},"GET"},{});
    p.FollowRedirect({101},std::nullopt);
    assert(s.pending==kMaxPendingChecks&&down.follows==6);
    s.pending=0;
    p.OnReceiveRedirect({{"https://same.test/sxg"},"GET",true},{});
    p.FollowRedirect({102},std::nullopt);
    assert(s.pending==0&&down.follows==7);
  }
  std::cout<<"PASS exact native redirect-hop methods: deny, unchanged forwarding, native cross-origin override, site disable, deadline, bounded late result, cancellation, custom rule and overload/unlive metrics\n";
}
