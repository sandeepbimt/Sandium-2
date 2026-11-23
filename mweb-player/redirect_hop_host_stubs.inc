#include <algorithm>
#include <cassert>
#include <cstdint>
#include <deque>
#include <functional>
#include <iostream>
#include <memory>
#include <optional>
#include <string>
#include <tuple>
#include <type_traits>
#include <utility>
#include <vector>
#define FROM_HERE 0
namespace base {
struct TimeDelta {
  int n=0;
  constexpr bool is_zero()const{return n==0;}
  friend bool operator<(TimeDelta a,TimeDelta b){return a.n<b.n;}
  friend TimeDelta operator-(TimeDelta a,TimeDelta b){return {a.n-b.n};}
};
constexpr TimeDelta Milliseconds(int n){return {n};}
static int clock=0;
struct TimeTicks {
  int n=0;
  static TimeTicks Now(){return {clock};}
  friend TimeDelta operator-(TimeTicks a,TimeTicks b){return {a.n-b.n};}
};
template<class T> struct WeakPtr {
  T* ptr=nullptr; std::weak_ptr<int> alive;
  WeakPtr()=default;
  WeakPtr(T* p,std::weak_ptr<int> l):ptr(p),alive(l){}
  explicit operator bool()const{return ptr&&!alive.expired();}
  T* operator->()const {return *this?ptr:nullptr;}
  T& operator*()const {return *operator->();}
};
template<class T> struct WeakPtrFactory {
  T* ptr; std::shared_ptr<int> alive=std::make_shared<int>(1);
  explicit WeakPtrFactory(T* p):ptr(p){}
  WeakPtr<T> GetWeakPtr(){return {ptr,alive};}
};
template<class F,class... P>
auto BindOnce(F f,P... params) {
  return [f,parts=std::tuple<P...>(std::move(params)...)](auto&&... more) mutable {
    std::apply([&](auto&... early) {
      if constexpr(std::is_member_function_pointer_v<F>) {
        auto& w=std::get<0>(parts);
        if(!w)return;
      }
      std::invoke(f,std::move(early)...,std::forward<decltype(more)>(more)...);
    },parts);
  };
}
template<class S> struct Callback;
template<class R,class... T> struct Callback<R(T...)> {
  std::function<R(T...)> impl;
  Callback()=default;
  template<class F> Callback(F v):impl(std::move(v)){}
  explicit operator bool()const{return bool(impl);}
  R Run(T... values) const {return impl(std::forward<T>(values)...);}
};
template<class S> using RepeatingCallback=Callback<S>;
using RepeatingClosure=Callback<void()>;
using OnceClosure=Callback<void()>;
struct OneShotTimer {
  OnceClosure fn;
  TimeDelta budget;
  template<class F> void Start(int,TimeDelta delta,F callback){budget=delta;fn=std::move(callback);}
  void Stop(){fn={};}
  void Fire(){auto f=std::exchange(fn,{});f.Run();}
};
}
struct GURL {
  std::string text;
  bool SchemeIsHTTPOrHTTPS()const{return text.starts_with("https://")||text.starts_with("http://");}
  const std::string& spec()const{return text;}
};
namespace url {
struct Origin {};
std::string GetOrigin(const GURL& u){
  auto i=u.text.find("://"); return u.text.substr(0,u.text.find('/',i+3));
}
bool IsSameOriginWith(const GURL& a,const GURL& b){return GetOrigin(a)==GetOrigin(b);}
}
namespace net {
struct MutableNetworkTrafficAnnotationTag {};
struct RedirectInfo {
  GURL new_url;
  std::string new_method;
  bool is_signed_exchange_fallback_redirect=false;
};
enum RequestPriority { LOW };
enum {ERR_BLOCKED_BY_CLIENT=-20,ERR_INVALID_ARGUMENT=-4,ERR_UNEXPECTED=-9,ERR_FAILED=-2};
}
namespace mojo_base { struct BigBuffer {}; }
namespace mojo {
struct Signals {bool closed; bool peer_closed() const{return closed;}};
struct MessagePipeHandle {bool* closed=nullptr; Signals QuerySignalsState()const{return {closed&&*closed};}};
struct MessagePipe {MessagePipeHandle h; const MessagePipeHandle& get()const{return h;}};
struct ScopedDataPipeConsumerHandle {};
template<class T> struct PendingRemote {
  T* ptr=nullptr; MessagePipe pipe;
  const MessagePipe& Pipe()const{return pipe;}
  bool is_valid()const{return ptr!=nullptr;}
};
template<class T> struct PendingReceiver {T* impl=nullptr; bool is_valid()const{return true;}};
template<class T> struct Remote {
  T* ptr=nullptr; bool connected=true;
  Remote()=default;
  explicit Remote(PendingRemote<T> p):ptr(p.ptr){}
  T* operator->(){assert(ptr);return ptr;}
  auto BindNewPipeAndPassReceiver(){return PendingReceiver<T>{};}
  template<class F> void set_disconnect_handler(F&&){}
  bool is_connected()const{return connected;}
  void ResetWithReason(uint32_t,const std::string&){connected=false;}
};
template<class T> struct Receiver {
  T* impl;
  explicit Receiver(T* p):impl(p){}
  auto BindNewPipeAndPassRemote(){return PendingRemote<T>{impl,{}};}
  template<class F> void set_disconnect_handler(F&&){}
};
template<class T> struct Owned {
  T* impl=nullptr;
  void Close(){}
  template<class F> void set_connection_error_with_reason_handler(F&&){}
};
template<class T> using SelfOwnedReceiverRef=Owned<T>*;
template<class T,class I> SelfOwnedReceiverRef<T> MakeSelfOwnedReceiver(std::unique_ptr<I>,PendingReceiver<T>){return nullptr;}
}
namespace network {
struct HttpRequestHeadersUpdateParams {int sentinel=0;};
struct ResourceRequest {};
struct URLLoaderCompletionStatus {
  int error_code;
  bool should_collapse_initiator=false;
  explicit URLLoaderCompletionStatus(int e):error_code(e){}
};
namespace mojom {
using EarlyHintsPtr=std::unique_ptr<int>;
using URLResponseHeadPtr=std::unique_ptr<int>;
struct URLLoader {
  virtual ~URLLoader()=default;
  virtual void FollowRedirect(HttpRequestHeadersUpdateParams,const std::optional<GURL>&)=0;
  virtual void SetPriority(net::RequestPriority,int32_t)=0;
};
struct URLLoaderClient {
  using OnUploadProgressCallback=base::OnceClosure;
  virtual ~URLLoaderClient()=default;
  virtual void OnReceiveEarlyHints(EarlyHintsPtr)=0;
  virtual void OnReceiveResponse(URLResponseHeadPtr,mojo::ScopedDataPipeConsumerHandle,
                                 std::optional<mojo_base::BigBuffer>)=0;
  virtual void OnReceiveRedirect(const net::RedirectInfo&,URLResponseHeadPtr)=0;
  virtual void OnUploadProgress(int64_t,int64_t,OnUploadProgressCallback)=0;
  virtual void OnTransferSizeUpdated(int32_t)=0;
  virtual void OnComplete(const URLLoaderCompletionStatus&)=0;
};
struct URLLoaderFactory {
  void CreateLoaderAndStart(mojo::PendingReceiver<URLLoader>,int32_t,uint32_t,
      const ResourceRequest&,mojo::PendingRemote<URLLoaderClient>,
      const net::MutableNetworkTrafficAnnotationTag&){}
};
}
}
enum class Resource {kImage,kScript};
enum class Action {kAllow,kBlock,kUnsupportedAction};
constexpr auto kCheckTimeout=base::Milliseconds(50);
constexpr int kMaxPendingChecks=32;
using ScopedUserRuleQuery=base::RepeatingCallback<bool(GURL,int,url::Origin,
        std::string,base::Callback<void(bool)>)>;
struct RuleSnapshot {void Evaluate(){}};
struct State {
  int pending=0;
  bool attempted=true, failed=false;
  std::deque<base::Callback<void(Action)>> jobs;
  std::vector<std::string> targets;
  struct Snapshot {
    State* state;
    auto& AsyncCall(void (RuleSnapshot::*)()){return *this;}
    auto& WithArgs(GURL target,Resource,url::Origin,const std::string&){
      state->targets.push_back(target.text);return *this;}
    template<class F>void Then(F f){state->jobs.emplace_back(std::move(f));}
  } snapshot{this};
  void Reply(Action a){
    auto cb=std::move(jobs.front()); jobs.pop_front();cb.Run(a);
  }
};
State& GetState(){static State s;return s;}
