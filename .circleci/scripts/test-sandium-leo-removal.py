#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).with_name('apply-sandium-leo-removal.py');sp=importlib.util.spec_from_file_location('patch',p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_method_not_callsite(self):
  s='    if (isLeoEnabled()) { keep(); }\n    private boolean isLeoEnabled() { return true; }\n'
  self.assertEqual(m.method(s,'isLeoEnabled'),'    if (isLeoEnabled()) { keep(); }\n\n')
 def test_nested_blocks(self):self.assertEqual(m.block('prefix if (a) { if(b) {foo();} } suffix','if (a)'), 'prefix  suffix')
 def test_else_retains_normal_browsing(self):self.assertEqual(m.ifelse('if (a) { leo(); } else { normal(); }','if (a)',True),' normal(); ')
 def test_repeat_method_idempotent(self):
  s='    public void leo() { x(); }\n    public void normal() {}'
  r=m.method(s,'leo');self.assertEqual(r,m.method(r,'leo'));self.assertIn('normal()',r)
 def test_builder_removes_orphans_preserves_normal_suggestions(self):
  s='''class Builder {
    private int getTileNavSuggestPosition(List<DropdownItemViewInfo> items) {
        for (int i = 0; i < items.size(); i++) { if (items.get(i).type == 7) { return i; } }
        return items.size();
    }
    void initDefaultProcessors() {
        super.initDefaultProcessors(context, host, textProvider, actionDelegate);
        if (host instanceof BraveSuggestionHost) {
            mBraveSearchBannerProcessor = new BraveSearchBannerProcessor();
            AutocompleteUIContext uiContext =
                    createUIContext(context, host, textProvider, actionDelegate);
            mBraveLeoSuggestionProcessor = new BraveLeoSuggestionProcessor(uiContext);
        }
    }
    public void buildDropdownViewInfoList() {
        super.buildDropdownViewInfoList(input, autocompleteResult);
        if (isBraveLeoEnabled()) {
            getTileNavSuggestPosition(viewInfoList);
        }
        if (isBraveSearchPromoBanner() && autocompleteEnabled) { normal(); }
        boolean enabled = mLeoAutocompleteDelegate.isAutoCompleteEnabled(tab.getWebContents());
    }
    @SuppressWarnings("UnusedVariable")
    private AutocompleteUIContext createUIContext(Context context) {
        assert false : "parent method used instead";
        return null;
    }
}
'''
  result=m.builder(s)
  for token in ('getTileNavSuggestPosition', 'uiContext', 'createUIContext', 'BraveLeo', 'isBraveLeoEnabled', '@SuppressWarnings'):
   self.assertNotIn(token,result)
  for token in ('super.initDefaultProcessors', 'super.buildDropdownViewInfoList', 'mBraveSearchBannerProcessor', 'isBraveSearchPromoBanner() && autocompleteEnabled', 'UserPrefs.get(tab.getProfile()).getBoolean(BravePref.AUTOCOMPLETE_ENABLED)'):
   self.assertIn(token,result)
  self.assertEqual(result,m.builder(result))
if __name__=='__main__':unittest.main()
