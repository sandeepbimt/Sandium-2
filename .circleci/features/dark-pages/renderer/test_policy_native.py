"""Compile actual policy helper against narrow API fakes, not Chromium itself."""
import json
from pathlib import Path
import subprocess
import tempfile
p = Path(__file__).resolve().parent
patch = next(x for x in json.loads((p/'patches.json').read_text()) if x['old'] == 'void ChromeContentBrowserClient::OverrideWebPreferences(')
helper = patch['new'].split('#if BUILDFLAG(IS_ANDROID)\n',1)[1].split('\n#endif',1)[0]
stub = r'''
#include <cassert>
#include <string>
namespace blink::mojom { enum class PreferredColorScheme { kLight, kDark }; }
struct GURL { std::string value; bool SchemeIsHTTPOrHTTPS() const {return value.starts_with("https://") || value.starts_with("http://");} };
struct Origin {bool is_opaque=false; bool opaque()const{return is_opaque;} };
namespace content { struct SiteInstance {}; }
struct Frame { content::SiteInstance* site; GURL url; Origin origin; bool error=false;
  content::SiteInstance* GetSiteInstance(){return site;} bool IsErrorDocument(){return error;}
  const Origin& GetLastCommittedOrigin(){return origin;} const GURL& GetLastCommittedURL(){return url;} };
struct WebContents { Frame* frame; bool client=true; int flags=0; std::string queried;
 Frame* GetPrimaryMainFrame(){return frame;} };
namespace night_mode {struct WebContentsThemeClient {
 WebContents* c; static WebContentsThemeClient* FromWebContents(WebContents* c) {static WebContentsThemeClient x;x.c=c;return c->client?&x:nullptr;}
 int SandiumDarkPageFlags(const GURL& url){c->queried=url.value;return c->flags;}
};}
struct WebPreferences {int sandium_dark_page_flags=-1;bool force_dark_mode_enabled=true;
 blink::mojom::PreferredColorScheme preferred_color_scheme=blink::mojom::PreferredColorScheme::kLight;
 blink::mojom::PreferredColorScheme preferred_root_scrollbar_color_scheme=blink::mojom::PreferredColorScheme::kLight;};
'''
main = r'''
int main(){
 content::SiteInstance a,b;
 Frame f{&a,{"https://a.example/path"},{false},false};
 WebContents c{&f,true,1,""};WebPreferences p;
 assert(ApplySandiumCommittedDarkPolicy(&c,a,&p));assert(c.queried==f.url.value);assert(p.sandium_dark_page_flags==1&&p.force_dark_mode_enabled);
 assert(!ApplySandiumCommittedDarkPolicy(&c,a,&p));
 c.flags=0;assert(ApplySandiumCommittedDarkPolicy(&c,a,&p));assert(p.force_dark_mode_enabled);
 p.sandium_dark_page_flags=1;c.client=false;assert(ApplySandiumCommittedDarkPolicy(&c,a,&p));assert(p.sandium_dark_page_flags==-1);
 c.client=true;c.flags=1;f.error=true;assert(!ApplySandiumCommittedDarkPolicy(&c,a,&p));assert(p.sandium_dark_page_flags==-1);
 f.error=false;f.origin.is_opaque=true;ApplySandiumCommittedDarkPolicy(&c,a,&p);assert(p.sandium_dark_page_flags==-1);
 f.origin.is_opaque=false;f.url.value="chrome://settings";ApplySandiumCommittedDarkPolicy(&c,a,&p);assert(p.sandium_dark_page_flags==-1);
 f.url.value="https://a.example/path";ApplySandiumCommittedDarkPolicy(&c,b,&p);assert(p.sandium_dark_page_flags==-1);
 f.site=&b;f.url.value="https://b.example/path";ApplySandiumCommittedDarkPolicy(&c,b,&p);assert(p.sandium_dark_page_flags==1&&c.queried==f.url.value);
 c.frame=nullptr;assert(ApplySandiumCommittedDarkPolicy(&c,b,&p));assert(p.sandium_dark_page_flags==-1);
}
'''
with tempfile.TemporaryDirectory() as t:
 src=Path(t)/'test.cc'; exe=Path(t)/'test';src.write_text(stub+helper+main)
 subprocess.run(['c++','-std=c++20','-Wall','-Wextra','-Werror',str(src),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('Actual helper compiled and mock-API assertions passed; NOT Chromium compile/navigation test')
