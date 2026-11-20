"""Check that the UI overlay cannot pass APK verification without native links."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'tools'))
import ci_prepare_raws_engine as graph

APK='//chrome/android:chrome_public_apk'
JAVA='//chrome/android:chrome_java'
RES='//chrome/android:chrome_app_java_resources'
MAIN='//chrome/android/java/src/org/chromium/chrome/browser/settings/MainSettings.java'
LIGHT='//chrome/android/java/res/values/raws_main_settings_palette.xml'
DARK='//chrome/android/java/res/values-night/raws_main_settings_palette.xml'
ENGINE='\n'.join(('//components/sandium_adblock:document_subresource_factory',
                  '//brave/third_party/rust/adblock/v0_13:lib',
                  '//chrome/browser:resources'))


class NativeUiGraph(unittest.TestCase):
    def test_both_palettes_and_java_must_be_reachable(self):
        sources=graph.ui_source_targets()
        response={(APK,'deps'):ENGINE+'\n'+'\n'.join(sources),
                  (JAVA,'deps'):RES,
                  ('//chrome/browser/ui/android/appmenu/internal:java','deps'):
                      '//chrome/browser/ui/android/appmenu/internal:java_resources'}
        response.update({(target,'sources'):'\n'.join(sorted(paths)) for target,paths in sources.items()})
        with tempfile.TemporaryDirectory() as tmp:
            receipt=Path(tmp)/'graph.txt'
            with patch.object(graph.subprocess,'check_output',
                              side_effect=lambda argv,**kwargs:response[tuple(argv[3:5])]):
                graph.verify_apk_graph(tmp,'gn','out',{},receipt,require_ui=True)
                self.assertIn(DARK,receipt.read_text())
                for key in ((JAVA,'sources'),(JAVA,'deps'),(RES,'sources')):
                    old=response[key]
                    response[key]=LIGHT if key==(RES,'sources') else ''
                    receipt.unlink(missing_ok=True)
                    with self.assertRaisesRegex(ValueError,'APK graph lacks RawS UI (sources|resource dependency)'):
                        graph.verify_apk_graph(tmp,'gn','out',{},receipt,require_ui=True)
                    self.assertFalse(receipt.exists())
                    response[key]=old

    def test_original_engine_graph_does_not_need_ui(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(graph.subprocess,'check_output',return_value=ENGINE) as desc:
            graph.verify_apk_graph(tmp,'gn','out',{},Path(tmp)/'graph.txt')
            desc.assert_called_once()
