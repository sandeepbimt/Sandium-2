"""Build the actual adapter with small recording doubles; no simulated ad blocking."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
TYPES=[('MainFrame',0,'main_frame'),('SubFrame',1,'sub_frame'),('Stylesheet',2,'stylesheet'),('Script',3,'script'),('Image',4,'image'),('FontResource',5,'font'),('SubResource',6,'other'),('Object',7,'object'),('Media',8,'media'),('Worker',9,''),('SharedWorker',10,''),('Prefetch',11,''),('Favicon',12,'image'),('Xhr',13,'xhr'),('Ping',14,'ping'),('ServiceWorker',15,''),('CspReport',16,''),('PluginResource',17,''),('NavigationPreloadMainFrame',19,''),('NavigationPreloadSubFrame',20,''),('Json',21,'')]

class MatcherContract(unittest.TestCase):
    def test_forwarding(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d)
            def write(name,text):
                f=r/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text)
            write('url/gurl.h','#pragma once\n#include <string>\nstruct GURL {std::string spec()const{return "https://ads.test/p?q=1";} std::string host()const{return "ads.test";}};')
            write('url/origin.h','#pragma once\n#include <string>\nnamespace url { struct Origin { static Origin CreateFromNormalizedTuple(const char*,const char*,int){return {};} std::string host()const{return "page.test";}};}')
            write('third_party/blink/public/mojom/loader/resource_load_info.mojom-shared.h','#pragma once\nnamespace blink::mojom {enum class ResourceType {'+','.join('k%s=%d'%(n,i) for n,i,t in TYPES)+'};}')
            write('net/base/registry_controlled_domains/registry_controlled_domain.h','#pragma once\nnamespace net::registry_controlled_domains {enum Filter{INCLUDE_PRIVATE_REGISTRIES}; inline bool same; inline bool SameDomainOrHost(const url::Origin&,const url::Origin&,Filter){return false;} inline bool SameDomainOrHost(const GURL&,const url::Origin&,Filter f){if(f!=INCLUDE_PRIVATE_REGISTRIES) std::abort(); return same;}}')
            write('brave/components/brave_shields/core/common/adblock/rs/src/lib.rs.h','''#pragma once
#include <string>
namespace adblock {struct BlockerResult {std::string spec,host,source,type,method;bool third,skip,check;bool matched=false,has_exception=false,important=false;int filter=0,exception=0; struct Option{bool has_value=false;}; Option redirect{},rewritten_url{};};
struct Engine {BlockerResult matches(const std::string&a,const std::string&b,const std::string&c,const std::string&d,bool e,const std::string&f,bool g,bool h) const{return {a,b,c,d,f,e,g,h};}};}''')
            write('components/sandium_adblock/request_matcher.h',(HERE/'native/request_matcher.h').read_text())
            write('components/sandium_adblock/standard_merge.h',(HERE/'native/standard_merge.h').read_text())
            write('test.cc','''#include "components/sandium_adblock/request_matcher.h"
#include "net/base/registry_controlled_domains/registry_controlled_domain.h"
#include <cassert>
int main() { using R=blink::mojom::ResourceType; adblock::Engine engine;
struct Case {R r;const char* t;}; Case cases[] = {'''+','.join('{R::k%s,"%s"}'%(n,t) for n,i,t in TYPES)+''',{static_cast<R>(999),""}};
for(auto [r,t]: cases) for (bool s:{false,true}) for (bool m:{false,true}) for (bool e:{false,true}) {
net::registry_controlled_domains::same=s;
auto x=sandium::adblock_native::MatchPass(engine,GURL{},r,url::Origin{},"POST",m,e);
assert(x.spec=="https://ads.test/p?q=1" && x.host=="ads.test" && x.source=="page.test");
assert(x.type==t && x.method=="POST" && x.third==!s && x.skip==(m||e) && x.check==!e);
}}''')
            exe=r/'test';subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-Wall','-Wextra','-Werror','-I'+str(r),str(HERE/'native/request_matcher.cc'),str(r/'test.cc'),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
