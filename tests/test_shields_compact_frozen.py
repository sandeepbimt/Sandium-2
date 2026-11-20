"""Frozen compact Shields order, real tracer reuse and shipping DNS lint contract."""
import ast,gzip,importlib.util,json,re,subprocess,sys,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,R/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
p=load('compact_popup','.circleci/scripts/apply-sandium-shields-popup.py')
e=load('compact_element','.circleci/features/element-corrector/android/apply.py')
d=load('compact_dark','.circleci/scripts/apply-sandium-dark-pages.py')
class Compact(unittest.TestCase):
 def test_final_order_and_hidden_master_without_policy_mutation(self):
  base=(R/'tests/fixtures/dark-pages/brave'/p.LAYOUT).read_text()
  out=e.layout(d.layout(p.layout(base)))
  self.assertEqual(out,e.layout(d.layout(p.layout(out))))
  p.validate_layout(out)
  root=e.ET.fromstring(out);A=e.A
  self.assertEqual([root[i].get(A+'id') for i in (1,2,3,4)],['@+id/advanced_options_content','@+id/sandium_appearance_group','@+id/sandium_cookies_group','@+id/block_count_text'])
  self.assertEqual(root[-1].get(A+'visibility'),'gone')
  self.assertTrue(any(n.get(A+'id')=='@+id/shields_toggle_switch' for n in root[-1].iter()))
  for card in (root[1],root[2],root[3]):
   self.assertTrue(any(n.get(A+'background')=='#18F5F5F5' for n in card))
  self.assertEqual(root[4].get(A+'background'),'@android:color/transparent')
 def test_stage_two_lint_is_addressed_without_changing_pinned_row_layout(self):
  base=(R/'tests/fixtures/dark-pages/brave'/p.LAYOUT).read_text()
  root=e.ET.fromstring(e.layout(d.layout(p.layout(base))))
  A=e.A
  self.assertEqual(root[1].get(A+'background'),'@drawable/advanced_options_bg')
  self.assertEqual(root[1].get(A+'clipToOutline'),'true')
  self.assertEqual(root[1][0].get(A+'id'),'@+id/trackers_item')
  self.assertFalse(any(n.get(A+'id')=='@+id/sandium_ads_group' for n in root.iter()))
  needs_compound_exception={n.get(A+'id') for n in root.iter()
     if 'UseCompoundDrawables' in n.get(e.TOOLS+'ignore','').split(',')}
  self.assertEqual(needs_compound_exception,
     {'@+id/'+n for n in ('trackers_item','block_element_item','cookies_item','shred_data_item')})
  for row in (n for n in root.iter() if n.get(A+'id') in needs_compound_exception):
   self.assertEqual((row[0].tag,row[0].get(A+'layout_weight')),('TextView','1'))
   self.assertEqual((row[1].tag,row[1].get(A+'layout_width'),row[1].get(A+'layout_height')),
                    ('ImageView','24dp','24dp'))
   self.assertEqual(row[1].get('{http://schemas.android.com/apk/res-auto}tint'),
                    '?attr/colorOnSurfaceVariant')
 def test_handler_reuses_toolbar_tracer_and_preserves_actions(self):
  base=(R/'tests/fixtures/dark-pages/brave'/p.JAVA).read_text()
  source=p.java(base);out=p.dns_ui(source)
  self.assertEqual(out,p.dns_ui(out))
  expected=next(n.value for n in ast.walk(ast.parse((R/'.circleci/scripts/apply-sandium-branding-refresh.py').read_text())) if isinstance(n,ast.Constant) and isinstance(n.value,str) and 'private static final class SandiumShieldsTracer' in n.value)
  self.assertIn(expected,out)
  self.assertIn('panel.addView(dns, footerIndex, dnsParams)',out)
  for control in ('cookies_item','shred_data_item'):
   self.assertIn('((View) mAdvancedOptionsContent.getParent()).findViewById(R.id.'+control+')',out)
  for write in ('setShieldsValue(', 'setShields(', 'setShieldsEnabled('):
   self.assertEqual(source.count(write),out.count(write))
 def test_shields_tap_dns_binding_matches_actual_inflated_include(self):
  A=e.A
  parent=e.ET.parse(R/'tests/fixtures/brave_unified_panel_layout.44a84b1.xml').getroot()
  outer_include=next(x for x in parent.iter('include')
                    if x.get('layout')=='@layout/brave_shields_tab_content')
  base=(R/'tests/fixtures/dark-pages/brave'/p.LAYOUT).read_text()
  comp=e.ET.fromstring(e.layout(d.layout(p.layout(base))))
  self.assertNotEqual(comp.get(A+'id'),outer_include.get(A+'id'))
  # LayoutInflater applies the explicit <include> ID after inflating the content.
  comp.set(A+'id',outer_include.get(A+'id'))
  live={v.get(A+'id'):v for v in comp.iter() if v.get(A+'id')}
  self.assertNotIn('@+id/shields_content_container',live)
  target=re.search(r'popupView\.findViewById\(R\.id\.(\w+)\)',p.DNS_BLOCK)[1]
  panel=live['@+id/'+target]
  self.assertEqual(panel.tag,'LinearLayout')
  footer=live['@+id/block_count_text']
  self.assertEqual(list(panel).index(footer),4)
  self.assertEqual(panel[3].get(A+'id'),'@+id/sandium_cookies_group')
  self.assertIn('sandiumContent instanceof LinearLayout panel',p.DNS_BLOCK)
  self.assertIn('panel.indexOfChild(mBlockCountText)',p.DNS_BLOCK)
  self.assertIn('if (footerIndex >= 0)',p.DNS_BLOCK)
 def test_dns_migrates_prior_placement_once(self):
  base=(R/'tests/fixtures/dark-pages/brave'/p.JAVA).read_text()
  out=p.dns_ui(p.java(base))
  for line in ('mAdvancedOptionsContent.addView(dns, dnsParams);',
               'panel.addView(dns, panel.getChildCount() - 2, dnsParams);'):
   legacy=('\n        '+p.DNS_MARKER+": independent of this site's Shields toggle."
           '\n        if (mAdvancedOptionsContent != null) {'
           '\n            '+line+'\n        }')
   self.assertEqual(p.dns_ui(out.replace(p.DNS_BLOCK,legacy)),out)
  self.assertEqual(p.dns_ui(out),out)
 def test_shipping_dns_resource_and_settings_management(self):
  adapter=load('compact_dns','experiments/secure-dns/adapter.py')
  fixture=json.loads(gzip.decompress((R/'experiments/secure-dns/fixtures/pinned.json.gz').read_bytes()))
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   for path,item in fixture['files'].items():
    q=root/path;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(item['source'])
   outputs=adapter.plan(root)
   ui=outputs[root/adapter.PACKAGE/'SandiumSecureDnsDropdown.java']
   strings=outputs[root/'chrome/browser/privacy/java/res/values/sandium_secure_dns_ui_strings.xml']
   self.assertNotIn('sandium_dns_ui_manage',strings+ui)
   self.assertNotIn('openSettings(',ui)
   self.assertIn('showGlobalNote ? R.string.sandium_dns_ui_global',ui)
   defined=set(re.findall(r'<string name="([^"]+)"',strings))
   refs=set(re.findall(r'R.string.(sandium_dns_ui_\w+)',ui))
   self.assertEqual(defined,refs)
   settings=outputs[root/adapter.SETTINGS]
   self.assertEqual(settings,(R/'experiments/secure-dns/java/SecureDnsSettings.java').read_text())
   self.assertIn('SandiumSecureDns.saveCustom(',settings)
 def test_group_contract_suite(self):
  result=subprocess.run([sys.executable,str(R/'.circleci/scripts/test-sandium-shields-groups.py')],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
if __name__=='__main__':unittest.main()
