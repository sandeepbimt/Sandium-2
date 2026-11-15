#!/usr/bin/env python3
"""Compile the exact transformed AddLinkTo body in a small C++ host harness.
This is not Chromium integration or a live sync test.
"""
from pathlib import Path
import importlib.util, subprocess, tempfile, sys
repo=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('home',repo/'.circleci/scripts/apply-sandium-home-shortcuts.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
source=m.manager(Path(sys.argv[1]).read_text())
start=source.index('bool CustomLinksManagerImpl::AddLinkTo(')
end=source.index('\nbool CustomLinksManagerImpl::AddLink(',start)
body=source[start:end]
assert 'current_links_.size() >= max_links_' in body
harness=r'''
#include <algorithm>
#include <cassert>
#include <optional>
#include <string>
#include <vector>
struct GURL {
 std::string value;
 bool is_valid() const { return !value.empty(); }
 bool operator==(const GURL& other) const { return value==other.value; }
};
namespace custom_links_util {
 template<class T> auto FindLinkWithUrl(std::vector<T>& list,const GURL& url) {
  return std::find_if(list.begin(),list.end(),[&](const T& x){return x.url==url;});
 }
}
struct CustomLinksManagerImpl {
 struct Link { GURL url; std::u16string title; bool is_most_visited; };
 std::vector<Link> current_links_, stored;
 std::optional<std::vector<Link>> previous_links_;
 size_t max_links_=200; bool initialized=true; int writes=0;
 bool IsInitialized() const { return initialized; }
 void StoreLinks() { stored=current_links_; ++writes; }
 bool AddLinkTo(const GURL&,const std::u16string&,size_t);
};
'''
tests=r'''
void fill(CustomLinksManagerImpl& m,size_t n) {
 for(size_t i=0;i<n;i++) m.current_links_.push_back({{"https://site"+std::to_string(i)+".test"},u"existing",false});
 m.stored=m.current_links_;
}
int main() {
 for(size_t n:{0,1,199,200,201,250}) {
  CustomLinksManagerImpl m;fill(m,n);
  bool added=m.AddLinkTo({"https://new.test"},u"new",n+99);
  assert(added==(n<200));
  assert(m.current_links_.size()==n+(n<200));
  assert(m.stored.size()==m.current_links_.size());
  assert(m.writes==(n<200?1:0));
  // Simulates preloaded sync/future-client state: no truncation or write on refusal.
  for(size_t i=0;i<n;i++) assert(m.current_links_[i].url.value=="https://site"+std::to_string(i)+".test");
  if(added) assert(m.current_links_.back().url.value=="https://new.test");
 }
 // Indexed insertion saves final newest-first placement with one write.
 CustomLinksManagerImpl original;
 for (int i=1;i<=26;i++) assert(original.AddLinkTo({"https://new"+std::to_string(i)+".test"},u"new",0));
 assert(original.writes==26);
 CustomLinksManagerImpl reconstructed;
 reconstructed.current_links_=original.stored; // Host model of native RetrieveLinks order.
 assert(reconstructed.current_links_.size()==26);
 for (int i=0;i<26;i++) assert(reconstructed.current_links_[i].url.value=="https://new"+std::to_string(26-i)+".test");
 CustomLinksManagerImpl m;fill(m,2);
 assert(!m.AddLinkTo({"https://site0.test"},u"duplicate",0));
 assert(!m.AddLinkTo({""},u"invalid",0));
 m.initialized=false;assert(!m.AddLinkTo({"https://new.test"},u"new",0));
 assert(m.writes==0 && m.current_links_.size()==2);
}
'''
with tempfile.TemporaryDirectory() as t:
 p=Path(t);(p/'test.cc').write_text(harness+body+tests)
 subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',str(p/'test.cc'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('PASS: exact patched AddLinkTo body, 0/1/199/200/201/250 entries, append, no over-limit truncation/write, duplicate/invalid/uninitialized rejection')
