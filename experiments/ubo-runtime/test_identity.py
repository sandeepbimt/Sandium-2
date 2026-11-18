import pathlib, runpy, subprocess, tempfile, unittest
ROOT=pathlib.Path(__file__).parent
m=runpy.run_path(str(ROOT/'identity/apply.py'))
class Identity(unittest.TestCase):
 def test_exact_source_guard_and_drift(self):
  raw=(ROOT/'identity/fixtures/web_auth_flow.cc').read_bytes()
  fixed=m['transform'](raw).decode()
  self.assertEqual(2,fixed.count('#elif BUILDFLAG(ENABLE_DESKTOP_ANDROID_EXTENSIONS)'))
  self.assertNotIn('static_assert(BUILDFLAG(ENABLE_DESKTOP_ANDROID_EXTENSIONS))',fixed)
  self.assertIn('delegate_->OnAuthFlowFailure(WebAuthFlow::Failure::CANNOT_CREATE_WINDOW)',fixed)
  with self.assertRaises(ValueError):m['transform'](raw+b'// drift')
 def test_core_only_actual_popup_body_compiles_and_fails_closed(self):
  fixed=m['transform']((ROOT/'identity/fixtures/web_auth_flow.cc').read_bytes()).decode()
  body=fixed.split('bool WebAuthFlow::DisplayAuthPageInPopupWindow() {',1)[1].split('\nvoid WebAuthFlow::BeforeUrlLoaded',1)[0]
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'test.cc'
   p.write_text('''#define BUILDFLAG(x) 0
struct Profile {};
struct BrowserWindowInterface { enum class CreationStatus { kOk }; };
BrowserWindowInterface::CreationStatus GetBrowserWindowCreationStatusForProfile(Profile&) {return BrowserWindowInterface::CreationStatus::kOk;}
struct WebAuthFlow { Profile* profile_; bool DisplayAuthPageInPopupWindow(); };
bool WebAuthFlow::DisplayAuthPageInPopupWindow() {'''+body+'''\nint main(){Profile p; WebAuthFlow flow{&p}; return flow.DisplayAuthPageInPopupWindow() ? 1 : 0;}\n''')
   subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror',str(p),'-o',str(p.with_suffix(''))],check=True)
   subprocess.run([str(p.with_suffix(''))],check=True)
 def test_source_plan_owns_both_directions(self):
  text=(ROOT/'source.py').read_text()
  self.assertIn("payload[src/auth['PATH']] = fixed_auth if enabled else raw_auth",text)
if __name__=='__main__':unittest.main()
