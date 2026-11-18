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
 def test_clang_actual_guarded_member_initializer_and_popup(self):
  raw=(ROOT/'identity/fixtures/web_auth_flow.cc').read_bytes()
  header=(ROOT/'identity/fixtures/web_auth_flow.h').read_bytes()
  fixed=m['transform'](raw).decode()
  fixed_header=m['transform_header'](header).decode()
  guard='#if BUILDFLAG(ENABLE_EXTENSIONS) || BUILDFLAG(ENABLE_DESKTOP_ANDROID_EXTENSIONS)'
  field=guard+fixed_header.split(guard,1)[1].split('#endif',1)[0]+'#endif'
  initializer=guard+fixed.split(guard,1)[1].split('#endif',1)[0]+'#endif'
  body=fixed.split('bool WebAuthFlow::DisplayAuthPageInPopupWindow() {',1)[1].split('\nvoid WebAuthFlow::BeforeUrlLoaded',1)[0]
  clang=runpy.run_path(str(ROOT/'identity/clang_check.py'))['diagnostics']
  flags=['-std=c++20','-Werror','-Wunreachable-code-return','-Wunused-private-field']
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'test.cc'
   for desktop,android in ((0,0),(1,0),(0,1)):
    prefix=f'#define ENABLE_EXTENSIONS {desktop}\n#define ENABLE_DESKTOP_ANDROID_EXTENSIONS {android}\n#define BUILDFLAG(x) x\n'
    # Use exact transformed field and initializer; supported configurations
    # retain and consume the gesture, core-only has neither storage nor init.
    text=prefix+'class Flow {public: Flow(bool user_gesture):\n'+initializer+'\n value_(0) {} int read() const {\n'+guard+'\n return user_gesture_;\n#else\n return value_;\n#endif\n} private:\n'+field+'\n int value_;};'
    # Supported configs must consume value_ as well to avoid a synthetic warning.
    text=text.replace('return user_gesture_;','return user_gesture_ + value_;')
    p.write_text(text)
    self.assertEqual([],clang(p,flags))
   # Exact popup body under core-only, including final-return placement.
   prefix='#define BUILDFLAG(x) 0\nstruct Profile {}; struct BrowserWindowInterface {enum class CreationStatus{kOk};}; BrowserWindowInterface::CreationStatus GetBrowserWindowCreationStatusForProfile(Profile&){return BrowserWindowInterface::CreationStatus::kOk;} struct WebAuthFlow{Profile* profile_; bool DisplayAuthPageInPopupWindow();}; bool WebAuthFlow::DisplayAuthPageInPopupWindow(){'
   p.write_text(prefix+body)
   self.assertEqual([],clang(p,flags))
   # Negative controls demonstrate these are real Clang warning checks.
   p.write_text('class Bad { private: bool user_gesture_; }; bool bad(){return false; return true;}')
   errors='\n'.join(clang(p,flags))
   self.assertIn('private field',errors)
   self.assertIn('return',errors)
  with self.assertRaises(ValueError):m['transform_header'](header+b'drift')
 def test_source_plan_owns_both_directions(self):
  text=(ROOT/'source.py').read_text()
  self.assertIn("payload[src/auth['PATH']] = fixed_auth if enabled else raw_auth",text)
if __name__=='__main__':unittest.main()
