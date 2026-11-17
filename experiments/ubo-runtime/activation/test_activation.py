import importlib.util,json,hashlib,subprocess,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('activation',HERE/'apply.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Activation(unittest.TestCase):
 def test_pair_and_reset(self):
  with tempfile.TemporaryDirectory() as td:
   core=Path(td);before={}
   for name,feature in m.FEATURES.items():before[name]=f'BASE_FEATURE({feature}, base::FEATURE_DISABLED_BY_DEFAULT);'
   before[m.FIELD]=m.OLD+'\nvariations::FeatureOverrides feature_overrides(*feature_list);\n'+ '\n'.join('feature_overrides.EnableFeature('+x+');' for x in ['features::kBraveAndroidExtensions','features::kWebContentsDiscard','features::kLazyBrowserInterfaceBroker','chrome::android::kLoadAllTabsAtStartup'])
   before[m.FACTORY]='''    if (!base::FeatureList::IsEnabled(features::kSandiumUboRuntime) ||
        !AreAndroidExtensionsAllowed()) return;
    if (!AreAndroidExtensionsAllowed() ||
        !base::FeatureList::IsEnabled(features::kSandiumUboRuntime) ||
        Exists(sandium_ubo::kExtensionId)) return;
'''
   before['browser/sources.gni']='brave_chrome_browser_public_deps = [\n]\n'
   manifest='{"incognito":"split"}'
   before['components/sandium_ubo/sandium_ubo/manifest.json']=manifest
   digest=hashlib.sha256(manifest.encode()).hexdigest()
   before['components/sandium_ubo/disk_resources.h']='kSandiumUboPayloadDigest[] = "'+('0'*64)+'";\n    {"manifest.json", IDR_SANDIUM_UBO_MANIFEST, "'+digest+'"},\n'

   for name,text in before.items():p=core/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
   with self.assertRaises(ValueError):m.apply(core,'main')
   self.assertFalse((core/m.RECEIPT).exists())
   m.verify(core,False);m.apply(core,'experiment/ubo-runtime');m.apply(core,'experiment/ubo-runtime')
   self.assertLess((core/m.FIELD).read_text().index(m.NEW),(core/m.FIELD).read_text().index('variations::FeatureOverrides'))
   m.reset(core);m.reset(core)
   for name,text in before.items():self.assertEqual((core/name).read_text(),text)
 def test_actual_preinit_expression_all_overrides(self):
  # Compile the literal emitted pre-init expression. No global FeatureList exists.
  code='''#include <cassert>
namespace base {enum State {FEATURE_DISABLED_BY_DEFAULT,FEATURE_ENABLED_BY_DEFAULT};
struct Feature {const char* name;State default_state;};
struct FeatureList {enum Override {OVERRIDE_DISABLE_FEATURE,OVERRIDE_ENABLE_FEATURE};int mask;
bool IsFeatureOverriddenFromCommandLine(const char* name,Override o){int i=name[0]=='r'?0:2;return mask&(1<<(i+(o==OVERRIDE_ENABLE_FEATURE)));}};}
namespace features {base::Feature kSandiumUboRuntime{"r",base::FEATURE_DISABLED_BY_DEFAULT};}
namespace sandium_ubo {base::Feature kSandiumUboExclusiveRouting{"e",base::FEATURE_DISABLED_BY_DEFAULT};}
int main(){for(int defaults=0;defaults<4;++defaults)for(int mask=0;mask<16;++mask){
features::kSandiumUboRuntime.default_state=static_cast<base::State>(defaults&1);
sandium_ubo::kSandiumUboExclusiveRouting.default_state=static_cast<base::State>((defaults>>1)&1);
base::FeatureList local{mask};auto* feature_list=&local;
'''+m.NEW+'''
bool expected=!(mask&1)&&(!(mask&4))&&((mask&2)||(defaults&1))&&((mask&8)||(defaults&2));
assert(sandium_ubo_enabled==expected);}}
'''
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'test.cc').write_text(code);subprocess.run(['g++','-std=c++17',str(p/'test.cc'),'-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
