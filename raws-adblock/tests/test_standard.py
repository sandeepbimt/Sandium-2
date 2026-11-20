import os, tempfile, subprocess, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class StandardRules(unittest.TestCase):
    def test_policy(self):
        code=r'''#include "standard_merge.h"
#include <cassert>
#include <memory>
using sandium::adblock_native::internal::MergeStandard;
struct Opt {bool has_value=false;int value=0;};
struct R {bool matched=false,important=false,has_exception=false;Opt redirect{},rewritten_url{};std::unique_ptr<int> filter,exception;};
int main(){
 for(bool third:{false,true}) for(bool hit:{false,true}) for(bool ex:{false,true})
 for(bool important:{false,true}) for(bool pm:{false,true}) for(bool pe:{false,true}) {
 R first;first.matched=hit;first.has_exception=ex;first.important=important;
 first.rewritten_url={true,42};first.redirect={true,17};first.filter=std::make_unique<int>(5);
 if(ex) first.exception=std::make_unique<int>(9);
 bool called=false;
 auto out=MergeStandard(std::move(first),third,pm,pe,[&](bool m,bool e){
    called=true; assert(m==(pm||(third&&hit))); assert(e==(pe||ex)); return R{};});
 assert(called==!(third&&important));assert(out.matched==(third&&hit));assert(out.has_exception==ex);
 assert(out.important==(third&&important));assert(!out.rewritten_url.has_value);
 assert(out.redirect.has_value==third);assert(bool(out.filter)==third);assert(bool(out.exception)==ex);
 }
 R a;a.matched=true;a.redirect={true,1};a.filter=std::make_unique<int>(1);
 auto b=MergeStandard(std::move(a),true,false,false,[](bool m,bool){assert(m);R r;r.redirect={true,2};r.rewritten_url={true,3};r.filter=std::make_unique<int>(2);return r;});
 assert(b.matched&&b.redirect.value==2&&b.rewritten_url.value==3&&*b.filter==2);
}'''
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'test.cc';f.write_text(code);exe=Path(d)/'test'
            subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-Wall','-Wextra','-Werror','-I'+str(ROOT/'native'),str(f),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
