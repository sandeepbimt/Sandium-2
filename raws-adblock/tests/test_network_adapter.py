"""Run the production match/decision functions with a recording bridge, not Rust."""
from pathlib import Path
import os, subprocess, tempfile, unittest, shutil

HERE = Path(__file__).resolve().parents[1]

class NetworkPolicy(unittest.TestCase):
    def test_matched_flags_and_final_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def write(name, source):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
            shutil.copytree(HERE/'native', root/'components/sandium_adblock')
            write('url/gurl.h', '''#pragma once
#include <string>
struct GURL {explicit GURL(std::string s):s(s) {} std::string s;
const std::string& spec()const{return s;} std::string host()const{return "fixture";}
bool is_valid()const{return s.starts_with("https://") || s.starts_with("http://") || s.starts_with("file:");}
bool SchemeIsHTTPOrHTTPS()const{return s.starts_with("https://")||s.starts_with("http://");}};''')
            write('url/origin.h', '''#pragma once
#include <string>
struct GURL;
namespace url {struct Origin {std::string h;const std::string& host()const{return h;}
bool opaque()const{return h.empty();} std::string scheme()const{return h=="file"?"file":"https";}
static Origin CreateFromNormalizedTuple(std::string s,std::string h,int p){
 if(s!="https" || p!=443){ std::abort(); } return {h};}};}''')
            write('net/base/registry_controlled_domains/registry_controlled_domain.h','''#pragma once
namespace net::registry_controlled_domains {
 enum Filter{INCLUDE_PRIVATE_REGISTRIES}; inline bool same_party_for_request;
 inline bool SameDomainOrHost(const GURL&,const url::Origin&,Filter){return same_party_for_request;}
 inline bool SameDomainOrHost(const url::Origin& a,const url::Origin& b,Filter){
 return a.host()==b.host() || a.host()=="m."+b.host();}}''')
            write('third_party/blink/public/mojom/loader/resource_load_info.mojom-shared.h','''#pragma once
namespace blink::mojom {enum class ResourceType {kMainFrame,kSubFrame,kStylesheet,kScript,kFavicon,kImage,kFontResource,kSubResource,kObject,kMedia,kXhr,kPing};}''')
            write('brave/components/brave_shields/core/common/adblock/rs/src/lib.rs.h','''#pragma once
#include <string>
namespace adblock {struct Opt{bool has_value=false;std::string value;};
struct BlockerResult{bool matched=false,important=false,has_exception=false;Opt redirect,rewritten_url;int filter=0,exception=0;};
struct Engine { BlockerResult supplied; mutable bool third=false; mutable int calls=0;
BlockerResult matches(const std::string&,const std::string&,const std::string&,const std::string&,bool t,const std::string&,bool,bool)const{third=t;++calls;return supplied;}};}''')
            write('check.cc','''#include "components/sandium_adblock/subresource_decision.h"
#include "net/base/registry_controlled_domains/registry_controlled_domain.h"
#include <cassert>
using namespace sandium::adblock_native;
int main(){
 for(auto name:{"m.youtube.com","youtube.com","notyoutube.com","youtube.com.evil.test",""}) {
  for(bool same : {false,true}) {
   net::registry_controlled_domains::same_party_for_request=same;
   adblock::Engine a,b; a.supplied.matched=true; a.supplied.important=true;
   auto x=MatchStandard(a,b,GURL("test"),blink::mojom::ResourceType::kScript,url::Origin{name},"GET");
   bool keep=!same || std::string(name)=="youtube.com" || std::string(name)=="m.youtube.com";
   assert(x.matched==keep && x.important==keep);assert(a.calls==1 && a.third==!same);
   assert(b.calls==(keep?0:1));
  }
 }
 // Full rule/exception/important truth table across original and alias passes.
 for(unsigned bits=0;bits<64;++bits){adblock::BlockerResult x;
  const MatchHistory before{bool(bits&1),bool(bits&2),bool(bits&4)};
  x.matched=bits&8;x.has_exception=bits&16;x.important=bits&32;
  auto h=ResolveDecision(x,before,"POST",true).history;
  assert(h.rule==bool(bits&9));assert(h.exception==bool(bits&18));assert(h.important==bool(bits&36));
  assert(h.blocked()==(bool(bits&36) || (bool(bits&9) && !bool(bits&18))));
 }
 for(std::string method:{"GET","HEAD","OPTIONS","POST","PUT","PATCH","DELETE","get"})
 for(bool alias:{false,true}) for(bool valid:{false,true}) for(bool present:{false,true}){
  adblock::BlockerResult x; x.rewritten_url={present,valid?"https://safe.test/path":"INVALID"};
  x.redirect={present,"data:text/plain,x"};auto out=ResolveDecision(x,{},method,alias);
  bool safe=method=="GET" || method=="HEAD" || method=="OPTIONS";
  assert(out.rewritten_url.has_value()==(!alias && valid && present && safe));
  if(out.rewritten_url) assert(*out.rewritten_url=="https://safe.test/path");
  assert(out.mock_data_url==(present?"data:text/plain,x":""));
 }
 using A=SubresourceAction;
 using R=blink::mojom::ResourceType;
 adblock::Engine d,e;
 const std::string url="https://target.test/a";
 const url::Origin site{"origin.test"};
 auto check=[&](R kind, const std::string& method="GET"){
  return DecideDocumentSubresource(&d,&e,GURL(url),kind,site,method);
 };
 net::registry_controlled_domains::same_party_for_request=false;
 assert(DecideDocumentSubresource(nullptr,&e,GURL(url),R::kScript,site,"GET")==A::kNotEvaluated);
 assert(DecideDocumentSubresource(&d,nullptr,GURL(url),R::kScript,site,"GET")==A::kNotEvaluated);
 assert(DecideDocumentSubresource(&d,&e,GURL("file:/foo"),R::kScript,site,"GET")==A::kNotEvaluated);
 assert(DecideDocumentSubresource(&d,&e,GURL("invalid"),R::kScript,site,"GET")==A::kNotEvaluated);
 assert(DecideDocumentSubresource(&d,&e,GURL("https://target.test/"+std::string(65536,'a')),R::kScript,site,"GET")==A::kNotEvaluated);
 assert(DecideDocumentSubresource(&d,&e,GURL(url),R::kScript,url::Origin{""},"GET")==A::kNotEvaluated);
 assert(DecideDocumentSubresource(&d,&e,GURL(url),R::kScript,url::Origin{"file"},"GET")==A::kNotEvaluated);
 assert(check(R::kMainFrame)==A::kNotEvaluated && check(R::kSubFrame)==A::kNotEvaluated);
 assert(check(R::kPing)==A::kNotEvaluated && check(R::kXhr)==A::kNotEvaluated);
 assert(check(R::kScript,"POST")==A::kNotEvaluated && check(R::kScript,"OPTIONS")==A::kNotEvaluated);
 assert(d.calls==0 && e.calls==0);
 for (auto kind : {R::kScript,R::kStylesheet,R::kImage,R::kFontResource}) assert(check(kind)==A::kAllow);
 d.supplied.matched=true;
 assert(check(R::kScript,"HEAD")==A::kBlock);
 e.supplied.has_exception=true;
 assert(check(R::kScript)==A::kAllow);
 e.supplied.has_exception=false;
 e.supplied.redirect={true,"data:text/plain,replacement"};
 assert(check(R::kScript)==A::kUnsupportedAction);
 e.supplied.redirect={false,""};
 e.supplied.rewritten_url={true,"https://target.test/b"};
 assert(check(R::kScript)==A::kUnsupportedAction);
 e.supplied.rewritten_url={false,""};
 d.supplied.important=true;
 e.supplied.has_exception=true;
 assert(check(R::kScript)==A::kBlock);

}''')
            exe=root/'check'
            subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-Wall','-Wextra','-Werror',
                            '-I'+str(root), str(HERE/'native/request_matcher.cc'),
                            str(HERE/'native/subresource_decision.cc'),str(root/'check.cc'),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
