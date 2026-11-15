#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest
HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('search',HERE/'apply-sandium-search-choices.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
FIX=HERE.parent.parent/'tests/fixtures/search-choices'
class SearchChoicesTest(unittest.TestCase):
    def test_pinned_transform_and_idempotence(self):
        for path,old,new in [(m.QUICK,m.OLD_QUICK,m.NEW_QUICK),(m.ADAPTER,m.OLD_FILTER,m.NEW_FILTER)]:
            source=(FIX/Path(path).name).read_text()
            result=m.replace(source,old,new)
            self.assertEqual(result,m.replace(result,old,new))
            self.assertIn(new,result)
            self.assertEqual(source.replace(old,'',1),result.replace(new,'',1))
    def test_drift_fails(self):
        with self.assertRaises(ValueError):m.replace('unknown',m.OLD_QUICK,m.NEW_QUICK)
    def test_choice_filter_is_not_default_mutation(self):
        self.assertNotIn('setSearchEngine',m.NEW_FILTER)
        self.assertNotIn('getShortName',m.NEW_FILTER.split('continue;')[0])
        self.assertIn('":br"',m.NEW_FILTER)
    def test_strip_cannot_be_reenabled_by_old_preference(self):
        self.assertIn('return false;',m.NEW_QUICK)
        self.assertNotIn('readBoolean',m.NEW_QUICK)
    def test_active_migration_is_narrow_and_profile_specific(self):
        source=(FIX/'BraveSearchEngineAdapter.java').read_text()
        for old,new in [(m.OLD_ACTIVE,m.NEW_ACTIVE),(m.OLD_START,m.NEW_START),(m.OLD_LOADED,m.NEW_LOADED)]:
            source=m.replace(source,old,new)
            self.assertEqual(source,m.replace(source,old,new))
        self.assertIn('!sandiumService.isDefaultSearchManaged()',source)
        self.assertIn('setDSEPrefs(candidate.getShortName(), profile);',source)
        self.assertIn('":br".equals(templateUrl.getKeyword())',source)
        self.assertIn('":g".equals(candidate.getKeyword())',source)
        self.assertNotIn('getPrimaryOTRProfile',m.NEW_ACTIVE)
    def test_v2_immutable_and_legacy_lists_both_filtered(self):
        source=(FIX/'SearchEngineAdapter.java').read_text()
        result=m.replace(source,m.OLD_LIST,m.NEW_LIST)
        self.assertEqual(result,m.replace(result,m.OLD_LIST,m.NEW_LIST))
        self.assertEqual(result.count('removeIf(engine ->'),2)
if __name__=='__main__':unittest.main()
