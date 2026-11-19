import gzip,hashlib,importlib.util,json,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]; MODULE=ROOT/'experiments/autofill-off'
spec=importlib.util.spec_from_file_location('autofill_ui',MODULE/'ui.py'); ui=importlib.util.module_from_spec(spec);spec.loader.exec_module(ui)
FIX=json.loads(gzip.decompress((MODULE/'ui-fixtures.json.gz').read_bytes())); F=FIX['files']
def method(s,name):
    pos=s.index(name+'('); start=s.rfind('\n',0,pos)+1; brace=s.index('{',pos); depth=1;i=brace+1
    while depth:
        depth+=(s[i]=='{')-(s[i]=='}');i+=1
    return s[start:i]
class Tests(unittest.TestCase):
 def test_exact_source_replay(self):
    for name,body in F.items():self.assertEqual(hashlib.sha256(body.encode()).hexdigest(),FIX['sha256'][name])
    for p in (ui.FRAGMENT,ui.BINDER,ui.XML):
        old=F[pathlib.Path(p).name]; new=ui.transform(p,old)
        self.assertEqual(new,ui.transform(p,new));self.assertNotEqual(old,new)
    xml=ui.transform(ui.XML,F['autofill_options_preferences.xml'])
    self.assertNotIn('RadioButtonGroupThirdPartyPreference',xml)
    self.assertIn('android:persistent="false"',xml);self.assertIn('android:defaultValue="false"',xml)
    self.assertIn('@string/autofill_third_party_filling_opt_in',xml)
    self.assertIn('app:primaryText="@string/autofill_third_party_filling_opt_in"',F['radio_button_group_third_party_preference.xml'])
    self.assertIn('RegisterBooleanPref(kAutofillUsingPlatformAutofill, false)',F['autofill_prefs.cc'])
    with self.assertRaises(ValueError):ui.transform(ui.BINDER,F['AutofillOptionsViewBinder.java'].replace('int currentOption','int drift'))
 def test_actual_confirmation_and_listener(self):
    s=F['AutofillOptionsMediator.java'];methods=[]
    for n in ('onThirdPartyToggleChanged','onConfirmWithRestart','showRestartConfirmation'):
        # declarations, not previous call sites
        marker={'onThirdPartyToggleChanged':'    private void onThirdPartyToggleChanged(', 'onConfirmWithRestart':'    private void onConfirmWithRestart(', 'showRestartConfirmation':'    private void showRestartConfirmation('}[n]
        methods.append(method(s[s.index(marker):],n))
    binder=ui.transform(ui.BINDER,F['AutofillOptionsViewBinder.java'])
    body=binder.split('(_, newValue) -> {',1)[1].split('});',1)[0]
    body=body.replace('model.get(ON_THIRD_PARTY_TOGGLE_CHANGED)\n                                        .onResult((boolean) newValue);','onThirdPartyToggleChanged((boolean) newValue);')
    java='''public class AutofillUiHarness {
 static final int THIRD_PARTY_AUTOFILL_ENABLED=1,HISTOGRAM_USE_THIRD_PARTY_FILLING=2;
 static class PropertyModel { boolean value; boolean get(int k){return value;} void set(int k,boolean v){value=v;} }
 static class Pref {static final int AUTOFILL_USING_PLATFORM_AUTOFILL=3;}
 static class Prefs {boolean value;void setBoolean(int k,boolean v){value=v;}}
 static class AutofillClientProviderUtils {static int updates;static void updatePackageUsedForAutofill(Prefs p,boolean v){updates++;}}
 static class RecordHistogram {static void recordBooleanHistogram(int k,boolean v){}}
 static class ModalDialogType {static final int APP=1;}
 static class ModalDialogManager {int shows;void showDialog(PropertyModel m,int type){shows++;}}
 PropertyModel mModel=new PropertyModel(), confirmation=new PropertyModel(); Prefs stored=new Prefs();
 ModalDialogManager manager=new ModalDialogManager();
 java.util.function.Supplier<ModalDialogManager> mModalDialogManagerSupplier=()->manager;
 java.util.function.Supplier<PropertyModel> mRestartConfirmationDialogModelSupplier=()->confirmation;
 int restarts; Runnable mRestartRunnable=()->restarts++;
 Prefs prefs(){return stored;} void updateToggleStateFromPref(){mModel.value=stored.value;}
 boolean click(Object newValue){ BODY }
 METHODS
 static void check(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[] args){
 AutofillUiHarness h=new AutofillUiHarness();check(!h.stored.value);
 check(!h.click(true));check(h.manager.shows==1 && h.mModel.value && !h.stored.value && h.restarts==0);
 h.updateToggleStateFromPref();check(!h.mModel.value); // native cancel/dismiss
 h.click(true);h.onConfirmWithRestart();check(h.stored.value && h.restarts==1);
 h.updateToggleStateFromPref();check(h.mModel.value); // existing explicit ON survives
 h.click(false);h.onConfirmWithRestart();check(!h.stored.value && h.restarts==2);
 h.manager=null;h.click(true);check(!h.mModel.value && !h.stored.value && h.restarts==2);
 h.manager=new ModalDialogManager();h.click(false);check(h.manager.shows==0); // redundant
 check(AutofillClientProviderUtils.updates==2);
 }
}'''.replace('BODY',body).replace('METHODS','\n'.join(methods))
    with tempfile.TemporaryDirectory() as td:
        p=pathlib.Path(td)/'AutofillUiHarness.java';p.write_text(java)
        subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main',str(p)],check=True,capture_output=True)
        subprocess.run(['java','-cp',td,'AutofillUiHarness'],check=True,capture_output=True)
 def test_storage_and_platform_flow_untouched(self):
    # No migration/store operations in UI plan. Preserve native authority including policy,
    # provider chooser, package tracking, restart, and existing explicit platform opt-in.
    mediator=F['AutofillOptionsMediator.java']
    self.assertIn('Settings.ACTION_REQUEST_SET_AUTOFILL_SERVICE',mediator)
    self.assertIn('NOT_ALLOWED_BY_POLICY',mediator)
    self.assertIn('mRestartRunnable.run()',mediator)
    self.assertNotIn('AutofillOptionsMediator.java',(MODULE/'ui.py').read_text())
if __name__=='__main__':unittest.main()
