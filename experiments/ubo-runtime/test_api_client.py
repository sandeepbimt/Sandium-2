import pathlib, runpy, subprocess, tempfile, unittest
ROOT=pathlib.Path(__file__).parent
m=runpy.run_path(str(ROOT/'api-client/apply.py'))
class ApiClient(unittest.TestCase):
 def test_pinned_guard_and_unchanged_stub(self):
  raw=(ROOT/'api-client/fixtures/chrome_extensions_api_client_android.cc').read_bytes()
  fixed=m['transform'](raw).decode()
  self.assertEqual(raw.decode().split('namespace extensions {')[1],fixed.split('namespace extensions {')[1])
  self.assertNotIn('static_assert(BUILDFLAG(ENABLE_DESKTOP_ANDROID_EXTENSIONS))',fixed)
  with self.assertRaises(ValueError):m['transform'](raw+b'// drift')
 def test_actual_translation_unit_core_only(self):
  fixed=m['transform']((ROOT/'api-client/fixtures/chrome_extensions_api_client_android.cc').read_bytes()).decode()
  with tempfile.TemporaryDirectory() as td:
   d=pathlib.Path(td)
   headers={
    'chrome/browser/extensions/api/chrome_extensions_api_client.h': '#include <memory>\nnamespace content {class WebContents{};} namespace extensions {class UsbDevicePermissionsPrompt{}; class ChromeExtensionsAPIClient {public: std::unique_ptr<UsbDevicePermissionsPrompt> CreateUsbDevicePermissionsPrompt(content::WebContents*) const;};}\n',
    'base/notimplemented.h':'',
    'build/build_config.h':'#define BUILDFLAG(x) BUILDFLAG_INTERNAL_##x()\n#define BUILDFLAG_INTERNAL_IS_ANDROID() 1\n',
    'extensions/buildflags/buildflags.h':'#define BUILDFLAG_INTERNAL_ENABLE_EXTENSIONS_CORE() 1\n#define BUILDFLAG_INTERNAL_ENABLE_DESKTOP_ANDROID_EXTENSIONS() 0\n'}
   for name,text in headers.items():
    p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
   p=d/'test.cc';p.write_text(fixed+'\nint main(){extensions::ChromeExtensionsAPIClient c; return c.CreateUsbDevicePermissionsPrompt(nullptr) ? 1 : 0;}\n')
   subprocess.run(['g++','-std=c++20','-Wall','-Werror','-I'+str(d),str(p),'-o',str(d/'test')],check=True)
   subprocess.run([str(d/'test')],check=True)
if __name__=='__main__':unittest.main()
