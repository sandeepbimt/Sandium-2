"""Active RawS Home hint source, run as real Java with faked Chrome inputs."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
OWNER=('chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/'
       'omnibox/HintTextUpdater.java')
RECIPE=ROOT/'raws-adblock/production-restore-recipe.json'

class HintTest(unittest.TestCase):
    def test_actual_update_path(self):
        entry=json.loads(RECIPE.read_text())['files'][OWNER]
        data=(ROOT/'raws-adblock/production-postimages'/entry['after_sha256']).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),entry['after_sha256'])
        src=data.decode()
        methods=src[src.index('    @Override\n    public void onUrlChanged('):
                    src.index('    private void onSearchEngineServiceChanged')]
        methods+=src[src.index('    private void updateHintText()'):
                     src.index('    private String getOmniboxHintText()')]
        h='''class Hint implements Events {
    static class ContextUtils {
      static String name = "io.github.sandeepbimt.raws";
      static ContextUtils getApplicationContext(){return new ContextUtils();}
      String getPackageName(){return name;}
    }
    static class Location {
      boolean tab=true, privateTab=false, home=true, visible=true;
      boolean hasTab(){return tab;}
      boolean isOffTheRecord(){return privateTab;}
      boolean getCurrentGurl(){return home;}
      Location getNewTabPageDelegate(){return this;}
      boolean isCurrentlyVisible(){return visible;}
    }
    static class UrlUtilities{static boolean isNtpUrl(boolean h){return h;}}
    static class OverrideMode { boolean controlled; boolean isEmbedderControlledHint(){return controlled;} }
    static class Input {
      String text="";
      boolean conventional=true, site=false;
      boolean isConventionalRequestType(){return conventional;}
      Object getSiteSearchData(){return site ? this : null;}
      int getDisplayState(){return 0;}
      String getUserText(){return text;}
    }
    static class TextUtils {static boolean isEmpty(String s){return s==null||s.isEmpty();}}
    static class DisplayState {static int SUGGESTIONS=1;}
    static class R {static class string {static int omnibox_empty_hint=1;}}
    static class Resources {String getString(int i){return "Search or type URL";}}
    static class AiModeButtonUiConfig {String placeholderText="AI";}
    static class SearchEngineService {
      String name;
      java.util.function.Supplier<AiModeButtonUiConfig> getAiModeButtonUiConfigSupplier(){return ()->null;}
    }
    final Resources mResourceProvider=new Resources();
    final Location mLocationBarDataProvider=new Location();
    final OverrideMode mEmbedderUiOverrides=new OverrideMode();
    SearchEngineService mSearchEngineService;
    Input mCurrentInput;
    boolean mRawSHomeHintApplied;
    String shown;
    interface HintSink {void onResult(String hint);}
    HintSink mUpdateHintTextCallback=hint->shown=hint;
    java.util.function.Supplier<Boolean> mActivationChipSelectedSupplier=()->false;
    String getOmniboxHintText(){return "Search "+mSearchEngineService.name+" or type URL";}
    boolean useAimActivationOrEmptyHint(){return false;}
    boolean triggerOrAlreadyShowingActivationHint(){return false;}
    String getAimActivationHintWithSpan(String hint){return hint;}
    boolean isSuggestionsPopover(){return false;}
    boolean isConventionalSearchFocused(){return false;}
    ''' + methods + '''
    void expect(String expected) {
      if (!expected.equals(shown)) throw new AssertionError("expected "+expected+", got "+shown);
    }
    public static void main(String[] args){
      Hint t=new Hint();
      final String generic="Search or type URL";
      t.onNtpStartedLoading(); t.expect(generic);
      t.mSearchEngineService=new SearchEngineService();
      for (String engine : new String[]{"Google","Bing","DuckDuckGo","Yahoo",""}) {
        t.mSearchEngineService.name=engine;
        t.updateHintText(); t.expect(generic);
        t.mCurrentInput=new Input();
        t.updateHintText(); t.expect(generic);
        t.mCurrentInput.text="words"; t.updateHintText();
        t.mCurrentInput.text=""; t.updateHintText(); t.expect(generic);
        t.mCurrentInput.site=true; t.updateHintText(); t.expect("");
        t.mCurrentInput=null; t.updateHintText(); t.expect(generic);
      }
      t.mSearchEngineService.name="Bing";
      t.mLocationBarDataProvider.home=false;
      t.onUrlChanged(false); t.expect("Search Bing or type URL");
      t.mLocationBarDataProvider.home=true;
      t.mLocationBarDataProvider.visible=false;
      t.onNtpStartedLoading(); t.expect("Search Bing or type URL");
      t.mLocationBarDataProvider.visible=true;
      t.onNtpStartedLoading(); t.expect(generic);
      t.mLocationBarDataProvider.privateTab=true;
      t.onIncognitoStateChanged(); t.expect("Search Bing or type URL");
      t.mLocationBarDataProvider.privateTab=false;
      t.mEmbedderUiOverrides.controlled=true;
      t.onIncognitoStateChanged(); t.expect("Search Bing or type URL");
      t.mEmbedderUiOverrides.controlled=false;
      ContextUtils.name="org.chromium.chrome";
      t.updateHintText(); t.expect("Search Bing or type URL");
    }
}
interface Events {
 void onUrlChanged(boolean changing);
 void onNtpStartedLoading();
 void onIncognitoStateChanged();
}
'''
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'Hint.java';p.write_text(h)
            subprocess.run([shutil.which('java'),str(p)],check=True)

if __name__=='__main__':
    unittest.main()
