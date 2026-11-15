"""Compile actual new FrameLoader policy block inside a fake lifecycle harness."""
import json
from pathlib import Path
import subprocess
import tempfile
here=Path(__file__).resolve().parent
patch=next(p for p in json.loads((here/'patches.json').read_text()) if p['path'].endswith('/frame_loader.cc'))
block=patch['new'][patch['new'].index('  if (commit_reason'):patch['new'].index('  tls_version_warning_origins_.clear();')]
stub=r'''
#include <cassert>
enum class CommitReason {kRegular,kXSLT,kJavaScript};
struct Settings {int custom=-1;bool force=true;int writes=0;void SetSandiumDarkPageFlagsForCommit(int f){custom=f;++writes;}void SetForceDarkModeEnabled(bool f){force=f;}};
struct Frame {bool main=true;Settings settings;bool IsOutermostMainFrame(){return main;}Settings* GetSettings(){return &settings;}};
struct Params {int sandium_dark_page_flags=-1;};
struct Harness {Frame frame;bool installed=false;
 void Commit(Params* navigation_params,CommitReason commit_reason,bool detached,bool swapped){
  // These guards model the existing upstream gates. Their actual source order
  // is separately asserted by test_renderer.py, not reimplemented Chromium.
  if(!detached || !swapped)return;
  auto* frame_=&frame;
'''
end=r'''
  installed=true;
 }
};
int main(){
 Harness h;Params on{1},off{0},unmanaged{-1};
 h.Commit(&on,CommitReason::kRegular,false,true);assert(!h.installed&&h.frame.settings.writes==0);
 h.Commit(&on,CommitReason::kRegular,true,false);assert(!h.installed&&h.frame.settings.writes==0);
 h.Commit(&on,CommitReason::kRegular,true,true);assert(h.installed&&h.frame.settings.custom==1&&h.frame.settings.force);
 h.Commit(&off,CommitReason::kRegular,true,true);assert(h.frame.settings.custom==0&&h.frame.settings.force);
 h.Commit(&on,CommitReason::kRegular,true,true);
 h.Commit(&off,CommitReason::kXSLT,true,true);assert(h.frame.settings.custom==1);
 h.Commit(&off,CommitReason::kJavaScript,true,true);assert(h.frame.settings.custom==1);
 h.frame.main=false;h.Commit(&off,CommitReason::kRegular,true,true);assert(h.frame.settings.custom==1);
 h.frame.main=true;h.Commit(&unmanaged,CommitReason::kRegular,true,true);assert(h.frame.settings.custom==-1&&h.frame.settings.force);
}
'''
with tempfile.TemporaryDirectory() as temp:
 src=Path(temp)/'test.cc';exe=Path(temp)/'test';src.write_text(stub+block+end)
 subprocess.run(['c++','-std=c++20','-Wall','-Wextra','-Werror',str(src),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('Actual policy block compiled in fake detach/swap/commit harness. NOT real navigation/Chromium test.')
