import json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));import compose
class Port(unittest.TestCase):
 def test_native_policy(self):
    with tempfile.TemporaryDirectory() as d:
        exe=Path(d)/'policy';subprocess.run([os.getenv('CXX','c++'),'-std=c++20','-Wall','-Wextra','-Werror','-I'+str(ROOT),str(ROOT/'tests/check.cc'),'-o',str(exe)],check=True);subprocess.run([exe],check=True)
 def test_cosmetic_current_document(self):
    with tempfile.TemporaryDirectory() as d:
        exe=Path(d)/'cosmetic_document';subprocess.run([os.getenv('CXX','c++'),'-std=c++20','-Wall','-Wextra','-Werror',str(ROOT/'tests/cosmetic_document_harness.cc'),'-o',str(exe)],check=True);subprocess.run([exe],check=True)
 def test_cold_cosmetic_readiness(self):
    with tempfile.TemporaryDirectory() as d:
        exe=Path(d)/'cosmetic_readiness';subprocess.run([os.getenv('CXX','c++'),'-std=c++20','-Wall','-Wextra','-Werror','-I'+str(ROOT),str(ROOT/'tests/cosmetic_readiness_harness.cc'),'-o',str(exe)],check=True);subprocess.run([exe],check=True)
    source=compose.local('native_api.cc.inc')
    retry=source.index('s.cosmetic_waiters.Push')
    self.assertTrue(source.index('void QueryHideStyles(') < retry < source.index('bool CheckSubframe('))
    self.assertEqual(source.count('cosmetic_waiters.Push'),1)
    finish=compose.local('refresh.cc.inc')
    self.assertLess(finish.index('state.ready = ready;'),finish.index('state.cosmetic_waiters.Finish('))
    self.assertIn('document.AsRenderFrameHostIfValid()',compose.local('cosmetic.cc.inc'))
    self.assertIn('target->GetLastCommittedURL() != url',compose.local('cosmetic.cc.inc'))
 def test_packaged_generic_provenance(self):
    packaged=ROOT.parent/'production-postimages/2d0f3968f88ded9441bfddf2284c3819d8de3018150fbd175afc49e2f116050a'
    self.assertEqual(compose.sha(packaged.read_bytes()),packaged.name)
    rules=set(packaged.read_text().splitlines())
    import re
    table=compose.local('style.h').split('kPackagedGenericAdSlots = {',1)[1].split('};',1)[0]
    selectors=re.findall(r'"([.#][A-Za-z_][A-Za-z0-9_-]*)"',table)
    self.assertEqual(len(set(selectors)),10)
    self.assertTrue(all('##'+selector in rules for selector in selectors))
 def test_simple_generic_census(self):
    with tempfile.TemporaryDirectory() as d:
        exe=Path(d)/'generic'
        subprocess.run([os.getenv('CXX','c++'),'-std=c++20','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT),str(ROOT/'tests/generic_harness.cc'),str(ROOT/'generic_style.cc'),'-o',str(exe)],check=True)
        packaged=ROOT.parent/'production-postimages/2d0f3968f88ded9441bfddf2284c3819d8de3018150fbd175afc49e2f116050a'
        subprocess.run([exe,packaged],check=True)
 def test_early_reference(self):
    with tempfile.TemporaryDirectory() as d:
        d=Path(d);(d/'adapted_early.inc').write_text(compose.adapt_early(compose.local('tests/reference/early_helpers.inc')));exe=d/'early';subprocess.run([os.getenv('CXX','c++'),'-std=c++20','-Wall','-Wextra','-Werror','-I'+str(d),str(ROOT/'tests/early_harness.cc'),'-o',str(exe)],check=True);subprocess.run([exe],check=True)
 def test_sealed_popup_uses_m158_dispositions(self):
    paths=(
        'chrome/browser/chrome_content_browser_client.cc',
        'content/browser/web_contents/web_contents_impl.cc',
    )
    manifest=json.loads((ROOT.parent/'production-restore-recipe.json').read_text())
    for path in paths:
        with self.subTest(path=path):
            oid=manifest['files'][path]['after_sha256']
            data=(ROOT.parent/'production-postimages'/oid).read_bytes()
            self.assertEqual(compose.sha(data),oid)
            for old,new in compose.POPUP_DISPOSITIONS.items():
                self.assertNotIn(('WindowOpenDisposition::'+old).encode(),data)
                self.assertIn(('WindowOpenDisposition::'+new).encode(),data)
 def test_navigation_lifecycle(self):
    with tempfile.TemporaryDirectory() as d:
        d=Path(d);(d/'adapted_nav.inc').write_text(compose.adapt_throttle(compose.local('tests/reference/popup_navigation.cc.inc')));exe=d/'flow';subprocess.run([os.getenv('CXX','c++'),'-std=c++20','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-I'+str(d),str(ROOT/'tests/flow_harness.cc'),'-o',str(exe)],check=True);subprocess.run([exe],check=True)
 def test_reference_navigation_port(self):
    s=compose.local('tests/reference/popup_navigation.cc.inc');self.assertEqual(compose.blob(s.encode()),compose.REFS['inc'][1]);result=compose.adapt_throttle(s)
    for token in ('WillStartRequest() override { return Check(); }','WillRedirectRequest() override { return Check(); }','remaining_budget_ -=','base::Milliseconds(100)','IsAboutBlank()','base::Seconds(10)','CANCEL_AND_IGNORE','QueryPopup(target, frame_','RemoveUserData(kSandiumPendingPopupKey)'):self.assertIn(token,result)
    self.assertNotIn('g_brave_browser_process',result)
 def test_catalog(self):
    rows=json.loads(compose.local('catalog.json'));self.assertEqual(len(rows),30);self.assertEqual(len({r['url'] for r in rows}),30)
    self.assertTrue(all(r['enabled_on_first_create'] for r in rows));self.assertEqual([r['url'].split('/')[-1] for r in rows if r['legacy_reenable_once']],['20.txt','21.txt','19.txt','22.txt'])
    self.assertTrue(rows[-1]['url'].endswith('/annoyances-others.txt'));self.assertTrue(all(r['url'].startswith('https://') for r in rows));self.assertEqual(compose.catalog_header(rows).count('  {'),30)
 def test_subscription_catalog_and_chromium_style(self):
    rows=json.loads(compose.local('catalog.json'))
    header=compose.catalog_header(rows)
    service=compose.local('subscription_service.h')
    definitions=compose.local('subscription_service.cc.inc')
    self.assertIn('explicit UrlSubscriptions(Profile* profile);',service)
    self.assertIn('~UrlSubscriptions() override;',service)
    self.assertNotIn('kCatalog[',service)
    self.assertEqual(service.count('kCatalog.at(i)'),6)
    self.assertIn('UrlSubscriptions::UrlSubscriptions(Profile* profile)',definitions)
    self.assertIn('UrlSubscriptions::~UrlSubscriptions() = default;',definitions)
    with tempfile.TemporaryDirectory() as d:
        d=Path(d)
        (d/'catalog_generated.h').write_text(header)
        (d/'check.cc').write_text(
            '#include "catalog_generated.h"\n'
            'static_assert(sandium::port1442::kCatalog.size() == 30);\n'
            'static_assert(sandium::port1442::kCatalog.at(29).key != nullptr);\n')
        subprocess.run([os.getenv('CXX','c++'),'-std=c++20','-Wall','-Wextra','-Werror',
                        '-fsyntax-only',str(d/'check.cc')],check=True)
 def test_drift(self):
    for bad in ['','abc xyz abc']:
        with self.assertRaises(ValueError):compose.once(bad,'abc','QRS')
 def test_no_fake_catalog(self):
    with self.assertRaises(ValueError):compose.verify_catalog('FILTERS=[]')
 def test_real_factory(self):
    path=ROOT.parent/'native/document_subresource_factory.cc';s=path.read_text();self.assertEqual(compose.blob(s.encode()),'d6becdd1813fdbbd88f2adf4786815253efa5d1c');out=compose.factory(s,'/* injected reference preprocessor */\n')
    self.assertNotIn('additional_.emplace(adblock::new_engine())',out);self.assertIn('if (!Install(std::move(additional))) return false;',out);self.assertIn('add_filter_list_with_permissions(bytes, 0)',out);self.assertIn('||ohjpfawpaap.in^$third-party,script,subdocument,image',out);self.assertIn('request.trusted_params || request.request_body',out)
    # While the original startup hook prewarms, normal navigation proceeds and
    # existing document factories can begin matching later without recreation.
    self.assertIn('if (!state.ready || state.pending',out)
    self.assertIn('state.ready = ready;',out)
    self.assertIn('if (!state.attempted || state.failed || document_origin.opaque()',out)
    self.assertIn('if(!s.ready || s.pending>=kMaxPendingChecks) return false;',out)
    producer=(ROOT/'compose.py').read_text()
    self.assertNotIn('OfflineStartupGate',producer)
    self.assertNotIn('startup.cc.inc',producer)
    self.assertNotIn('WhenOfflineRulesReady',out)
    self.assertNotIn('1500',out)
    self.assertNotIn('snapshot.AsyncCall(&RuleSnapshot::Install)',out)
    self.assertIn('state.refresh_candidate.AsyncCall(&RuleSnapshot::Initialize)',out)
    self.assertIn('state.snapshot = std::move(state.refresh_candidate);',out)
    self.assertIn('revision == state.refresh_revision',out)

 def test_refresh_replacement(self):
    source=compose.local('native_api.cc.inc')
    actual=source[source.index('void InstallAdditionalRules('):source.index('void QueryPopup(')]
    with tempfile.TemporaryDirectory() as d:
        d=Path(d); (d/'refresh_submit_actual.inc').write_text(actual)
        exe=d/'refresh'
        subprocess.run([os.getenv('CXX','c++'),'-std=c++20','-Wall','-Wextra','-Werror','-I'+str(ROOT),'-I'+str(d),str(ROOT/'tests/refresh_harness.cc'),'-o',str(exe)],check=True)
        subprocess.run([exe],check=True)
 def test_last_good_feed_cache(self):
    src=compose.local('native_api.cc.inc')
    inspect=src[src.index('std::optional<int> InspectSubscription('):src.index('void InstallAdditionalRules(')]
    src=compose.local('subscription_service.h')
    store=src[src.index('  static bool Accept('):src.index('  void Save(')]
    self.assertIn('url::Origin::Create(u) != source',src)
    self.assertIn('CredentialsMode::kOmit',src)
    with tempfile.TemporaryDirectory() as d:
        d=Path(d)
        (d/'inspect_subscription_actual.inc').write_text(inspect)
        (d/'feed_store_actual.inc').write_text(store)
        (d/'catalog_generated.h').write_text(compose.catalog_header(json.loads(compose.local('catalog.json'))))
        exe=d/'feeds'
        subprocess.run([os.getenv('CXX','c++'),'-std=c++20','-Wall','-Wextra','-Werror','-I'+str(d),str(ROOT/'tests/feed_cache_harness.cc'),'-o',str(exe)],check=True)
        subprocess.run([exe],check=True)
 def test_dom(self):
    # Real desktop Blink layout engine. The selectors are injected test inputs,
    # not an Android Mojo call or a real adblock-rust match.
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as d,sync_playwright() as pw:
        exe=Path(d)/'style';subprocess.run([os.getenv('CXX','c++'),'-std=c++20','-I'+str(ROOT),str(ROOT/'tests/check.cc'),'-o',str(exe)],check=True);css=subprocess.check_output([exe,'css'],text=True)
        browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-background-networking']);page=browser.new_page();page.set_content('''<div id="slot" class="ad-slot" style="height:90px"></div><div class="allow" style="height:28px"></div><button onclick="this.dataset.pressed=1">Play</button><button onclick="this.dataset.pressed=1">Change server</button>''');height=lambda sel:page.locator(sel).evaluate('(e)=>e.getBoundingClientRect().height');self.assertEqual(height('#slot'),90);page.add_style_tag(content=css);self.assertEqual(height('#slot'),0);self.assertEqual(height('.allow'),28);page.evaluate("document.body.insertAdjacentHTML('beforeend','<div data-creative style=\"height:60px\"></div>')");self.assertEqual(height('[data-creative]'),0)
        for title in ('Play','Change server'):
            b=page.get_by_role('button',name=title);b.click();self.assertEqual(b.get_attribute('data-pressed'),'1')
        print('PASS real Blink slot 90px -> 0px, excepted element 28px, late insert 0px, Play and Change server still clickable');browser.close()
if __name__=='__main__':unittest.main(verbosity=2)
