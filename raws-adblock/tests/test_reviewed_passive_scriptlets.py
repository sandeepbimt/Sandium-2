"""Detached passive-scriptlets admission and isolated effect probes (no Android)."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RECIPE = json.loads((ROOT / 'production-restore-recipe.json').read_bytes())['files']
VENDOR = 'brave/third_party/rust/chromium_crates_io/vendor/adblock-v0_13/src/cosmetic_filter_cache.rs'
POLICY = 'components/sandium_adblock/passive_scriptlet_policy.h'
RENDER = 'chrome/renderer/raws_passive_scriptlet_program.h'


def product(path):
    h = RECIPE[path]['after_sha256']
    raw = (ROOT / 'production-postimages' / h).read_bytes()
    if hashlib.sha256(raw).hexdigest() != h:
        raise ValueError(path)
    return raw.decode()


class ReviewedPassiveScriptlets(unittest.TestCase):
    def test_source_origin_bounds_and_exact_exceptions_policy(self):
        cxx = shutil.which('c++')
        if cxx is None:
            self.skipTest('C++ compiler absent')
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            (t/'policy.h').write_text(product(POLICY))
            src=t/'main.cc'
            src.write_text(r'''
#include <cassert>
#include "policy.h"
using namespace sandium::adblock_native::passive_scriptlets;
static_assert(EffectivePrograms(3, 3, 0) == 3);
static_assert(EffectivePrograms(3, 3, 1) == 2);
static_assert(EffectivePrograms(3, 3, 4) == 0);
static_assert(EffectivePrograms(0, 3, 0) == 0);
static_assert(EffectivePrograms(3, 0, 0) == 0);
static_assert(EffectivePrograms(3, 8, 0) == 0);
static_assert(EffectivePrograms(3, 3, 8) == 0);
static_assert(EffectivePrograms(1, 3, 2) == 1);
static_assert(IsPlainDomainList("publisher.test,sub.publisher.test"));
static_assert(!IsPlainDomainList("publisher.test,*.example"));
static_assert(!IsPlainDomainList("something*.test"));
static_assert(!IsPlainDomainList(".domain.test"));
static_assert(!IsPlainDomainList("example..test"));
static_assert(!IsPlainDomainList("169.254.169.254"));
static_assert(!IsPlainDomainList("bad-.test"));
int main() {
  using namespace std::string_literals;
  const auto positives = "publisher.test##+js(ra, data-popunder-url)\n"s +
      "two.test,sub.two.test##+js(remove-attr, data-ppcnt_ads, main[onclick])\n";
  const auto out = ReviewedSourceRules(
      positives +
      "publisher.test#@#+js()\n"
      "##+js(ra, data-popunder-url)\n"
      "~publisher.test##+js(ra, data-popunder-url)\n"
      "publisher.test##+js(ra, onclick)\n"
      "publisher.test##+js(ra, data-ppcnt_ads, main[onclick], stay)\n"
      "publisher.test##+js(ra, data-popunder-url, .ad)\n"
      "other.test##+js(ra, data-popunder-url);\n"
      "! publisher.test##+js(ra, data-popunder-url)\n");
  assert(out && *out == positives);
  assert(ReviewedSourceRules("host.test##+js(ra, data-popunder-url)\r\n") ==
         "host.test##+js(ra, data-popunder-url)\n");
  std::string many;
  for (int i=0;i<9;++i) many += positives;
  assert(!ReviewedSourceRules(many));
  assert(!ReviewedSourceRules(std::string((8u<<20)+1, 'x')));
}
''')
            exe=t/'test'
            subprocess.run([cxx,'-std=c++20','-Wall','-Wextra','-Werror',str(src),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

    def test_disjoint_native_seams_and_release_guards(self):
        browser=product('chrome/browser/chrome_content_browser_client.cc')
        factory=product('components/sandium_adblock/document_subresource_factory.cc')
        rust=product(VENDOR)
        self.assertIn('BASE_FEATURE(kRawSReviewedPassiveScriptlets, base::FEATURE_DISABLED_BY_DEFAULT)', factory)
        self.assertIn('source.catalog_index == kReviewedPassiveAdsCatalogIndex', factory)
        self.assertIn('PruneSandiumSubscription(bytes);', factory)
        self.assertIn('primary->second | additional->second | source->second', factory)
        self.assertIn('current.refresh_revision', factory)
        self.assertIn('SensitiveCompoundPath', factory)
        self.assertIn('IsOffTheRecord()', browser)
        self.assertIn('frame->GetWeakDocumentPtr()', browser)
        self.assertIn('base::Milliseconds(300)', browser)
        self.assertIn('ContentSettingsType::JAVASCRIPT', browser)
        self.assertIn('void RawSCosmeticObserver::DOMContentLoaded', browser)
        for guard in ('!handle->IsServedFromBackForwardCache()',
                      '!handle->IsPrerenderedPageActivation()',
                      'entry && !entry->IsViewSourceMode()',
                      'passive_scriptlet_document_->AsRenderFrameHostIfValid() != frame'):
            self.assertIn(guard, browser)
        self.assertIn('raws_passive_scriptlet_deny |= 4', rust)
        self.assertIn('permission.to_bits() == 0', rust)
        self.assertLess(rust.index('// Process script uninjects'), rust.index('let mut raws_passive_scriptlet_allow = 0'))
        renderer=product('chrome/renderer/chrome_render_frame_observer.cc')
        hook=renderer.split('void ChromeRenderFrameObserver::RunRawSReviewedPassiveScriptlets(',1)[1].split('void ChromeRenderFrameObserver::',1)[0]
        for guard in ('IsInFencedFrameTree()', 'IsProvisional()', 'GetEmbeddingToken() != token',
                      'raws_passive_scriptlet_document_ == token', 'doc.IsSecureContext()',
                      'doc.GetSecurityOrigin().IsOpaque()', 'GURL(doc.Url()) != expected_url',
                      'passive::ValidPrograms', 'ISOLATED_WORLD_ID_RAWS_PASSIVE_SCRIPTLETS'):
            self.assertIn(guard, hook)
        self.assertNotIn('RequestExecuteScript(', hook)
        self.assertEqual(hook.count('ExecuteScriptInIsolatedWorld('), 1)
        self.assertIn('RAWS_PASSIVE_SCRIPTLET_NATIVE_PASS',
                      product('components/sandium_adblock/smoke1442.cc'))

    def test_dom_load_and_worker_admission_retry_with_actual_browser_methods(self):
        cxx = shutil.which('c++')
        if cxx is None:
            self.skipTest('C++ compiler absent')
        browser = product('chrome/browser/chrome_content_browser_client.cc')
        start = browser.index('void RawSCosmeticObserver::DOMContentLoaded(')
        end = browser.index('void RawSCosmeticObserver::OnWarmResult(', start)
        nav = browser.index('void RawSCosmeticObserver::DidFinishNavigation(')
        lifecycle = browser[nav:browser.index('  const bool owned', nav)]
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            (t/'methods.inc').write_text(
                browser[start:end] + lifecycle + '}\n')
            fixture = (Path(__file__).parent / 'fixtures' /
                       'passive_scriptlet_browser_lifecycle.cc')
            exe = t/'lifecycle'
            subprocess.run([cxx, '-std=c++20', '-Wall', '-Wextra', '-Werror',
                            '-I', str(t), str(fixture), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_static_programs_remove_only_bounded_matching_ad_metadata(self):
        node=shutil.which('node')
        if node is None:
            self.skipTest('Node compiler absent')
        source=product(RENDER)
        programs=[s.split(')RAWSREMOVE"',1)[0] for s in source.split('R"RAWSREMOVE(')[1:]]
        self.assertEqual(len(programs), 2)
        fixture=r'''
const assert=require('node:assert/strict'), vm=require('node:vm');
const code=__SOURCE__;
const html='http://www.w3.org/1999/xhtml';
const other='http://www.w3.org/2000/svg';
function element(localName, attrs, namespaceURI=html) {
 const set=new Set(attrs);
 return {namespaceURI,localName,
   hasAttribute(name){return set.has(name)},
   removeAttribute(name){set.delete(name)}};
}
function run(i,nodes,state='complete') {
 let pos=0;
 const document={documentElement:{}, readyState:state,
  createNodeIterator(root, filter) {
    assert.equal(filter, 1);
    return {nextNode(){return nodes[pos++]||null}};
  }};
 vm.runInNewContext(code[i],{document, NodeFilter:{SHOW_ELEMENT:1}});
 return pos;
}
const a='data-popunder-url', b='data-ppcnt_ads';
const pop=element('div',[a,b,'onclick','href','style']);
const custom=element('custom-widget',[a]);
const svg=element('svg',[a],other);
const customized=element('div',[a,'is']);
const main=element('main',[b,'onclick','href']);
const notMain=element('div',[b,'onclick']);
assert.equal(run(0,[pop,custom,svg,customized],'loading'),0);
assert.equal(pop.hasAttribute(a),true);
run(0,[pop,custom,svg,customized]);
assert.equal(pop.hasAttribute(a),false);
[custom,svg,customized].forEach(node=>assert.equal(node.hasAttribute(a),true));
['onclick','href','style',b].forEach(attr=>assert.equal(pop.hasAttribute(attr),true));
run(1,[main,notMain,pop]);
assert.equal(main.hasAttribute(b),false);
assert.equal(main.hasAttribute('onclick'),true);
assert.equal(main.hasAttribute('href'),true);
assert.equal(notMain.hasAttribute(b),true);
const cap=Array.from({length:20},()=>element('div',[a]));
run(0,cap);
assert.equal(cap.filter(e=>!e.hasAttribute(a)).length,16);
const scan=Array.from({length:4200},()=>element('div',[]));
scan[4100]=element('div',[a]);
assert.equal(run(0,scan),4096);
assert.equal(scan[4100].hasAttribute(a),true);
'''.replace('__SOURCE__', json.dumps(programs))
        subprocess.run([node,'-e',fixture],check=True)
