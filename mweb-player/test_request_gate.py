"""Compile #1514's unmodified decision function, with URL/engine doubles.
This measures whether matching is reached, not whether a real list matched.
Run from a complete clone or supply the exact postimage as the only argument.
"""
import hashlib, os, subprocess, sys, tempfile
from pathlib import Path
BASE='1bdd41e4c478459ca6b86b1717dac601e17c832b'
SHA='9e7fa353b10b7df6ae1fec8c6c019da0d06b76099663c2319e1633c069fe8210'
H='''#pragma once
#include <string>
namespace blink::mojom { enum class ResourceType {kScript,kStylesheet,kImage,kSubResource,kFavicon,kSubFrame,kXhr,kMedia,kPing,kFontResource,kMainFrame}; }
namespace adblock { struct Engine {}; }
struct GURL {std::string path;bool is_valid()const{return true;}bool SchemeIsHTTPOrHTTPS()const{return true;}const std::string& spec()const{return path;}};
namespace url {struct Origin {bool opaque()const{return false;}std::string scheme()const{return "https";}};}
namespace sandium::adblock_native {
enum class SubresourceAction{kNotEvaluated,kUnsupportedAction,kBlock,kAllow};
struct Match {struct Optional {bool has_value=false;}redirect,rewritten_url;};
inline unsigned calls=0;
inline Match MatchStandard(const adblock::Engine&,const adblock::Engine&,const GURL&,blink::mojom::ResourceType,const url::Origin&,const std::string&){++calls;return {};}
struct History {bool blocked()const{return false;}};struct Decision{History history;};
inline Decision ResolveDecision(Match,Match,const std::string&,bool){return {};}
}
'''
CASES=[('SABR transport','https://fixture.googlevideo.com/videoplayback','POST','kXhr',0),('player API','https://m.youtube.com/youtubei/v1/player','POST','kXhr',0),('QoE report','https://m.youtube.com/api/stats/qoe','POST','kXhr',0),('playback tracker','https://m.youtube.com/ptracking','GET','kXhr',1),('ordinary clip','https://fixture.googlevideo.com/videoplayback','GET','kMedia',1),('follow-on measurement','https://www.youtube.com/measurement/follow_on/fixture','GET','kImage',1),('HLS playlist','https://media.example/index.m3u8','GET','kXhr',1),('checkout fraud configuration','https://buy.tinypass.com/checkout/offer/getFraudPreventionConfig','POST','kXhr',0)]
def main():
    src=(Path(sys.argv[1]).read_bytes() if len(sys.argv)==2 else subprocess.check_output(['git','--no-replace-objects','show',BASE+':raws-adblock/production-postimages/'+SHA]))
    if hashlib.sha256(src).hexdigest()!=SHA: raise ValueError('wrong decision source')
    with tempfile.TemporaryDirectory() as td:
        d=Path(td);h=d/'components/sandium_adblock/subresource_decision.h';h.parent.mkdir(parents=True);h.write_text(H)
        main='\n#include <cassert>\n#include <iostream>\nint main(){using namespace sandium::adblock_native;using T=blink::mojom::ResourceType;adblock::Engine e;url::Origin o;\n'
        for label,url,method,typ,count in CASES:
            action='kAllow' if count else 'kNotEvaluated'
            main+=f'calls=0; assert(DecideDocumentSubresource(&e,&e,GURL{{"{url}"}},T::{typ},o,"{method}")==SubresourceAction::{action}); assert(calls=={count});std::cout<<"PASS {label}: matcher calls={count}\\n";\n'
        (d/'decision.cc').write_bytes(src+(main+'}\n').encode());exe=d/'test'
        subprocess.run([os.getenv('CXX','c++'),'-std=c++20','-Wall','-Wextra','-Werror','-I',td,str(d/'decision.cc'),'-o',str(exe)],check=True); subprocess.run([exe],check=True)
if __name__=='__main__':main()
