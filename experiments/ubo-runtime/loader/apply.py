#!/usr/bin/env python3
"""Install the isolated full-runtime loader overlay after EXT0 source replay.
No ad-engine cutover; does not claim runtime readiness.
"""
import argparse, base64, hashlib, json, re, zipfile, os, shutil, tempfile
from pathlib import Path
from xml.sax.saxutils import escape
HERE=Path(__file__).resolve().parent
BUNDLE_SHA='580afa3547a46422b3752759b5a90018ba7bfa4320770ea863950c78b29932d5'

def replace(p,old,new):
 s=p.read_text()
 if new in s:return
 if s.count(old)!=1:raise ValueError('Expected one anchor: '+str(p)+' '+old[:60])
 p.write_text(s.replace(old,new,1))

def disk_header(disk):
 payload_digest=hashlib.sha256('\n'.join(disk).encode()).hexdigest()
 return '#ifndef BRAVE_COMPONENTS_SANDIUM_UBO_DISK_RESOURCES_H_\n#define BRAVE_COMPONENTS_SANDIUM_UBO_DISK_RESOURCES_H_\n#include "brave/components/sandium_ubo/grit/sandium_ubo_resources.h"\nnamespace sandium_ubo {\nstruct DiskResource { const char* path; int id; const char* sha256; };\ninline constexpr char kSandiumUboPayloadDigest[] = "'+payload_digest+'";\ninline constexpr DiskResource kSandiumUboDiskResources[] = {\n'+'\n'.join(disk)+'\n};\n}\n#endif\n'

def build_disk_inventory(core):
 """Pure final inventory for a reviewed bridge's staged asset/map edits."""
 dest=core/'components/sandium_ubo'
 mapping=(dest/'resource_map.h').read_text()
 entries=re.findall(r'\{"sandium_ubo/([^"\n]+)", (IDR_SANDIUM_UBO_[A-Z0-9_]+)\}', mapping)
 if not entries or len(entries)!=mapping.count('{"sandium_ubo/'):
  raise ValueError('Invalid disk inventory resource map')
 paths=set();symbols=set();disk=[]
 for name,symbol in entries:
  if Path(name).is_absolute() or '..' in Path(name).parts or '\\' in name or name in paths or symbol in symbols:
   raise ValueError('Unsafe or duplicate disk inventory entry')
  paths.add(name);symbols.add(symbol)
  p=dest/'sandium_ubo'/name
  if p.is_symlink() or not p.is_file():raise ValueError('Missing disk resource')
  disk.append('    {"'+name+'", '+symbol+', "'+hashlib.sha256(p.read_bytes()).hexdigest()+'"},')
 return disk_header(disk)

def materialize(core,bundle):
 data=bundle.read_bytes()
 if hashlib.sha256(data).hexdigest()!=BUNDLE_SHA:raise ValueError('Unexpected prepared bundle')
 identity=json.loads((HERE/'identity.json').read_text())
 h=hashlib.sha256(base64.b64decode(identity['public_key'])).hexdigest()[:32]
 if ''.join(chr(ord('a')+int(c,16)) for c in h)!=identity['extension_id']:raise ValueError('Key identity mismatch')
 dest=core/'components/sandium_ubo';dest.mkdir(parents=True,exist_ok=True)
 files={}
 with zipfile.ZipFile(bundle) as z:
  for n in z.namelist():
   if Path(n).is_absolute() or '..' in Path(n).parts:raise ValueError('Unsafe bundle path')
   files[n]=z.read(n)
 manifest=json.loads(files['manifest.json']);manifest['key']=identity['public_key']
 # A fixed built-in identity, not an upstream signature or Web Store install.
 files['manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
 includes=[];mapping=[];disk=[]
 for i,(name,data) in enumerate(sorted(files.items())):
  p=dest/'sandium_ubo'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
  symbol='IDR_SANDIUM_UBO_MANIFEST' if name=='manifest.json' else 'IDR_SANDIUM_UBO_FILE_'+str(i)
  includes.append(f'      <include name="{symbol}" file="sandium_ubo/{escape(name)}" type="BINDATA" />')
  mapping.append('    {"sandium_ubo/'+name+'", '+symbol+'},')
  disk.append('    {"'+name+'", '+symbol+', "'+hashlib.sha256(data).hexdigest()+'"},')
 (dest/'disk_resources.h').write_text(disk_header(disk))
 for name in ['materializer.h','materializer.cc']:
  (dest/name).write_bytes((HERE/'native'/name).read_bytes())
 (dest/'resources.grd').write_text('''<?xml version="1.0" encoding="UTF-8"?>
<grit base_dir="." latest_public_release="0" current_release="1">
  <outputs>
    <output filename="grit/sandium_ubo_resources.h" type="rc_header">
      <emit emit_type="prepend"></emit>
    </output>
    <output filename="sandium_ubo_resources.pak" type="data_package" />
  </outputs>
  <release seq="1"><includes>
'''+ '\n'.join(includes)+'\n  </includes></release>\n</grit>\n')
 (dest/'resource_map.h').write_text('''#ifndef BRAVE_COMPONENTS_SANDIUM_UBO_RESOURCE_MAP_H_
#define BRAVE_COMPONENTS_SANDIUM_UBO_RESOURCE_MAP_H_
#include "brave/components/sandium_ubo/grit/sandium_ubo_resources.h"
#include "ui/base/webui/resource_path.h"
inline constexpr webui::ResourcePath kSandiumUboResources[] = {
'''+ '\n'.join(mapping)+'\n};\n#endif\n')
 (dest/'identity.h').write_text('''#ifndef BRAVE_COMPONENTS_SANDIUM_UBO_IDENTITY_H_
#define BRAVE_COMPONENTS_SANDIUM_UBO_IDENTITY_H_
namespace sandium_ubo {
inline constexpr char kExtensionId[] = "'''+identity['extension_id']+'''";
inline constexpr char kVersion[] = "'''+identity['version']+'''";
}  // namespace sandium_ubo
#endif
''')
 (dest/'BUILD.gn').write_text('''import("//brave/resources/brave_grit.gni")
import("//extensions/buildflags/buildflags.gni")
assert(is_android && enable_extensions_core)
source_set("identity") {
  sources = [ "identity.h" ]
}
source_set("materializer") {
  sources = [ "materializer.h", "materializer.cc", "disk_resources.h" ]
  deps = [ ":resources", "//base", "//crypto", "//extensions/common", "//ui/base" ]
}
source_set("resource_map") {
  sources = [ "resource_map.h" ]
  public_deps = [ ":resources", "//ui/base" ]
}
brave_grit("resources") {
  source = "resources.grd"
  outputs = [ "grit/sandium_ubo_resources.h", "sandium_ubo_resources.pak" ]
}
''')
 return identity

def apply_overlay(src,bundle):
 core=src/'brave';identity=materialize(core,bundle)
 replace(core/'resources/resource_ids.spec','  # WARNING: The IDs range is 2^16-1.', '''  "brave/components/sandium_ubo/resources.grd": {
    "META": {"sizes": {"includes": [700]}},
    "includes": [54200],
  },
  # WARNING: The IDs range is 2^16-1.''')
 replace(core/'brave_paks.gni','    if (enable_extensions) {', '''    if (is_android && enable_extensions_core) {
      sources += [ "$root_gen_dir/brave/components/sandium_ubo/sandium_ubo_resources.pak" ]
      deps += [ "//brave/components/sandium_ubo:resources" ]
    }
    if (enable_extensions) {''')
 replace(core/'browser/extensions/resources.gni','brave_extensions_resources = []', '''brave_extensions_resources = []
if (is_android && enable_extensions_core) {
  brave_extensions_resources += [
    "//brave/components/sandium_ubo:resources",
    "//brave/components/sandium_ubo:identity",
    "//brave/components/sandium_ubo:resource_map",
    "//brave/components/sandium_ubo:materializer",
  ]
}''')
 replace(core/'browser/brave_browser_features.h','BASE_DECLARE_FEATURE(kBraveAndroidExtensions);','BASE_DECLARE_FEATURE(kBraveAndroidExtensions);\nBASE_DECLARE_FEATURE(kSandiumUboRuntime);')
 replace(core/'browser/brave_browser_features.cc','BASE_FEATURE(kBraveAndroidExtensions, base::FEATURE_DISABLED_BY_DEFAULT);','BASE_FEATURE(kBraveAndroidExtensions, base::FEATURE_DISABLED_BY_DEFAULT);\nBASE_FEATURE(kSandiumUboRuntime, base::FEATURE_DISABLED_BY_DEFAULT);')
 field=core/'chromium_src/chrome/browser/chrome_browser_field_trials.cc'
 replace(field,'''  if (!feature_list->IsFeatureOverriddenFromCommandLine(
          features::kBraveAndroidExtensions.name,
          base::FeatureList::OVERRIDE_ENABLE_FEATURE)) {''','''  // This isolated product experiment enables its dependencies as one unit.
  // FeatureList is not installed yet: inspect this instance's command-line
  // overrides and the declared default, not static IsEnabled(). Explicit
  // disable wins; default-off diagnostic APKs remain off.
  const bool sandium_ubo_enabled =
      !feature_list->IsFeatureOverriddenFromCommandLine(
          features::kSandiumUboRuntime.name,
          base::FeatureList::OVERRIDE_DISABLE_FEATURE) &&
      (feature_list->IsFeatureOverriddenFromCommandLine(
           features::kSandiumUboRuntime.name,
           base::FeatureList::OVERRIDE_ENABLE_FEATURE) ||
       features::kSandiumUboRuntime.default_state == base::FEATURE_ENABLED_BY_DEFAULT);
  if (!sandium_ubo_enabled && !feature_list->IsFeatureOverriddenFromCommandLine(
          features::kBraveAndroidExtensions.name,
          base::FeatureList::OVERRIDE_ENABLE_FEATURE)) {''')
 replace(field,'  variations::FeatureOverrides feature_overrides(*feature_list);','  variations::FeatureOverrides feature_overrides(*feature_list);\n  if (sandium_ubo_enabled)\n    feature_overrides.EnableFeature(features::kBraveAndroidExtensions);')
 # ComponentLoader already friends BraveComponentLoader in pinned Brave patches.
 factory=core/'chromium_src/chrome/browser/extensions/component_loader_factory.cc'
 replace(factory,'''// BraveComponentLoader only loads the Brave extension, which is desktop-only.
using CurrentComponentLoader = extensions::ComponentLoader;''','''#include "base/feature_list.h"
#include "base/logging.h"
#include "base/functional/bind.h"
#include "base/memory/weak_ptr.h"
#include "base/task/sequenced_task_runner.h"
#include "chrome/browser/profiles/profile.h"
#include "extensions/browser/extension_file_task_runner.h"
#include "brave/components/sandium_ubo/materializer.h"
#include "brave/browser/brave_browser_features.h"
#include "brave/browser/extensions/android/brave_extension_management.h"
#include "brave/components/sandium_ubo/identity.h"
#include "brave/components/sandium_ubo/grit/sandium_ubo_resources.h"
namespace extensions {
class BraveComponentLoader : public ComponentLoader {
 public:
  explicit BraveComponentLoader(Profile* profile)
      : ComponentLoader(profile), profile_path_(profile->GetPath()) {
    // SANDIUM_UBO_PROFILE_INITIALIZATION
  }
  void Shutdown() override {
    weak_factory_.InvalidateWeakPtrs();
    ComponentLoader::Shutdown();
  }
  void AddDefaultComponentExtensions(bool skip_session_components) override {
    ComponentLoader::AddDefaultComponentExtensions(skip_session_components);
    if (!base::FeatureList::IsEnabled(features::kSandiumUboRuntime) ||
        !AreAndroidExtensionsAllowed() || Exists(sandium_ubo::kExtensionId) ||
        materialization_pending_)
      return;
    materialization_pending_ = true;
    extensions::GetExtensionFileTaskRunner()->PostTaskAndReplyWithResult(
        FROM_HERE,
        base::BindOnce(&sandium_ubo::PrepareComponent, profile_path_,
                       sandium_ubo::CaptureAssets()),
        base::BindOnce(&BraveComponentLoader::OnMaterialized,
                       weak_factory_.GetWeakPtr()));
  }
 private:
  void OnMaterialized(std::optional<sandium_ubo::PreparedComponent> component) {
    materialization_pending_ = false;
    if (!component) {
      LOG(ERROR) << "Sandium uBO verified materialization/localization failed";
      return;
    }
    if (!AreAndroidExtensionsAllowed() ||
        !base::FeatureList::IsEnabled(features::kSandiumUboRuntime) ||
        Exists(sandium_ubo::kExtensionId)) return;
    const auto id = Add(std::move(component->manifest), component->directory);
    if (id != sandium_ubo::kExtensionId) {
      if (!id.empty()) Remove(id);
      LOG(ERROR) << "Sandium uBO fixed identity registration failed";
    }
    // Registration is NOT proof that background listeners or filtering are ready.
  }
  const base::FilePath profile_path_;
  bool materialization_pending_ = false;
  base::WeakPtrFactory<BraveComponentLoader> weak_factory_{this};
};
}  // namespace extensions
using CurrentComponentLoader = extensions::BraveComponentLoader;''')
 allow=core/'chromium_src/chrome/browser/extensions/component_extensions_allowlist/allowlist.cc'
 replace(allow,'#include "extensions/common/constants.h"','#include "extensions/common/constants.h"\n#if BUILDFLAG(IS_ANDROID) && BUILDFLAG(ENABLE_EXTENSIONS_CORE)\n#include "brave/components/sandium_ubo/grit/sandium_ubo_resources.h"\n#include "brave/components/sandium_ubo/identity.h"\n#endif')
 replace(allow,'bool IsComponentExtensionAllowlistedBraveImpl(const std::string& extension_id) {', '''bool IsComponentExtensionAllowlistedBraveImpl(const std::string& extension_id) {
#if BUILDFLAG(IS_ANDROID) && BUILDFLAG(ENABLE_EXTENSIONS_CORE)
  if (extension_id == sandium_ubo::kExtensionId) return true;
#endif''')
 replace(allow,'bool IsComponentExtensionAllowlistedBraveImpl(int manifest_resource_id) {','''bool IsComponentExtensionAllowlistedBraveImpl(int manifest_resource_id) {
#if BUILDFLAG(IS_ANDROID) && BUILDFLAG(ENABLE_EXTENSIONS_CORE)
  if (manifest_resource_id == IDR_SANDIUM_UBO_MANIFEST) return true;
#endif''')
 mgr=core/'chromium_src/chrome/browser/extensions/chrome_component_extension_resource_manager.cc'
 replace(mgr,'#include <chrome/browser/extensions/chrome_component_extension_resource_manager.cc>','''#include "build/build_config.h"
#include "extensions/buildflags/buildflags.h"
#if BUILDFLAG(IS_ANDROID) && BUILDFLAG(ENABLE_EXTENSIONS_CORE)
#include "brave/components/sandium_ubo/resource_map.h"
#endif
#include <chrome/browser/extensions/chrome_component_extension_resource_manager.cc>''')
 native=src/'chrome/browser/extensions/chrome_component_extension_resource_manager.cc'
 replace(native,'  }();','''  }();
#if BUILDFLAG(IS_ANDROID) && BUILDFLAG(ENABLE_EXTENSIONS_CORE)
  AddComponentResourceEntries(kSandiumUboResources);
#endif''')
 policy=core/'browser/extensions/android/brave_extension_management.cc'
 replace(policy,'#include "base/feature_list.h"','#include "base/feature_list.h"\n#include "brave/components/sandium_ubo/identity.h"')
 replace(policy,'''    return AreAndroidExtensionsAllowed() ||
           Manifest::IsComponentLocation(extension.location());''','''    if (extension.id() == sandium_ubo::kExtensionId) {
      return Manifest::IsComponentLocation(extension.location()) &&
             AreAndroidExtensionsAllowed() &&
             base::FeatureList::IsEnabled(features::kSandiumUboRuntime);
    }
    // The isolated product runtime must not open arbitrary extension installs.
    return Manifest::IsComponentLocation(extension.location());''')
 print('SANDIUM_UBO_LOADER=STAGED version='+identity['version']+'; Brave remains active; runtime unverified')
# Receipt is outside brave because source.py resets that checkout independently.
STATE='.sandium-ubo-loader-state'
INPUTS=[
 'resources/resource_ids.spec','brave_paks.gni','browser/extensions/resources.gni',
 'browser/brave_browser_features.h','browser/brave_browser_features.cc',
 'chromium_src/chrome/browser/chrome_browser_field_trials.cc',
 'chromium_src/chrome/browser/extensions/component_loader_factory.cc',
 'chromium_src/chrome/browser/extensions/component_extensions_allowlist/allowlist.cc',
 'chromium_src/chrome/browser/extensions/chrome_component_extension_resource_manager.cc',
 'browser/extensions/android/brave_extension_management.cc',
]
NATIVE='chrome/browser/extensions/chrome_component_extension_resource_manager.cc'
def digest(data):return hashlib.sha256(data).hexdigest()
def safe_path(src,name):
 p=src/name
 if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('Unsafe receipt path')
 for node in [p,*p.parents]:
  if node==src:break
  if node.is_symlink():raise ValueError('Symlink in owned path: '+str(node))
 return p

def atomic_write(p,data):
 p.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.ubo-',dir=p.parent)
 try:
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(tmp,p)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def validate(src,receipt):
 if receipt.get('version')!=1:raise ValueError('Unsupported receipt')
 for name,e in receipt['files'].items():
  p=safe_path(src,name)
  current=digest(p.read_bytes()) if p.exists() else None
  if current not in [e['before'],e['after']]:raise ValueError('Unowned modification: '+name)
  for key in ['before','after']:
   h=e[key]
   if h is not None:
    b=src/STATE/'blobs'/h
    if b.is_symlink() or digest(b.read_bytes())!=h:raise ValueError('Corrupt ownership blob')
 # Reject unknown additions inside our newly-created component, including directories.
 root=src/'brave/components/sandium_ubo'
 allowed=set(receipt['files'])
 for name in list(allowed):allowed.update(str(p) for p in Path(name).parents)
 if root.exists():
  for p in root.rglob('*'):
   if p.is_symlink() or str(p.relative_to(src)) not in allowed:raise ValueError('Unowned component path: '+str(p))

def transition(src,receipt,key):
 validate(src,receipt) # Entire-tree preflight before any mutation.
 for name,e in receipt['files'].items():
  p=safe_path(src,name);h=e[key]
  if h is None:
   if p.exists():p.unlink()
  else:atomic_write(p,(src/STATE/'blobs'/h).read_bytes())
 if key=='before':
  root=src/'brave/components/sandium_ubo'
  if root.exists():
   for p in sorted(root.rglob('*'),key=lambda x:len(x.parts),reverse=True):
    if p.is_dir():p.rmdir()
   root.rmdir()

def apply(src,bundle):
 state=src/STATE;receipt_path=state/'receipt.json'
 if receipt_path.exists():
  receipt=json.loads(receipt_path.read_text())
  if receipt['bundle_sha']!=digest(bundle.read_bytes()):raise ValueError('Receipt bundle mismatch')
  transition(src,receipt,'after');return
 if (src/'brave/components/sandium_ubo').exists():raise ValueError('Unowned component exists without receipt')
 # Plan in isolation; failed anchors never partially modify the source tree.
 with tempfile.TemporaryDirectory(prefix='ubo-loader-plan-') as td:
  stage=Path(td);names=['brave/'+x for x in INPUTS]+[NATIVE]
  for name in names:
   original=safe_path(src,name);p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(original.read_bytes())
  apply_overlay(stage,bundle)
  receipt={'version':1,'bundle_sha':digest(bundle.read_bytes()),'files':{}}
  for p in sorted(stage.rglob('*')):
   if not p.is_file():continue
   name=str(p.relative_to(stage));original=safe_path(src,name)
   before=original.read_bytes() if original.exists() else None;after=p.read_bytes()
   if before==after:continue
   e={}
   for key,data in [('before',before),('after',after)]:
    e[key]=digest(data) if data is not None else None
    if data is not None:atomic_write(state/'blobs'/e[key],data)
   receipt['files'][name]=e
  # Durable receipt precedes first source write. A killed apply/reset is resumable.
  atomic_write(receipt_path,(json.dumps(receipt,sort_keys=True,indent=2)+'\n').encode())
  transition(src,receipt,'after')

def reset(src):
 p=src/STATE/'receipt.json'
 if not p.exists():
  if (src/'brave/components/sandium_ubo').exists():raise ValueError('Cannot reset unowned component')
  return
 receipt=json.loads(p.read_text());transition(src,receipt,'before')
 # Retain content-addressed backups; receipt deletion is the transaction commit.
 p.unlink()
 print('SANDIUM_UBO_LOADER=RESET')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--src',type=Path,required=True)
 p.add_argument('--bundle',type=Path);p.add_argument('--reset',action='store_true');a=p.parse_args()
 if a.reset:reset(a.src.resolve())
 elif a.bundle:apply(a.src.resolve(),a.bundle.resolve())
 else:p.error('--bundle is required unless --reset')
