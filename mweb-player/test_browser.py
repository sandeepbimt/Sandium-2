"""Offline desktop Chromium tests. Synthetic transport; real Response, JSON parser and video decoder."""
import base64, json, os, shutil, subprocess, tempfile, unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
JS = Path(__file__).with_name('player.js').read_text()
# Simulate the two HTTPS transports in an in-memory document. The native browser
# Response.json, JSON.parse, Blob and video decoder remain real. No network.
ORIGIN = 'https://m.youtube.com'; CDN = 'https://fixture.googlevideo.com/videoplayback'
GATE = '([on, origin])=>{const location={origin};return (' + JS + ")(on,'https://m.youtube.com')}"
AD = {'videoDetails': {'videoId': 'synthetic-content'}, 'playabilityStatus': {'status': 'OK'},
      'streamingData': {'adaptiveFormats': [{'url': CDN+'?content'}]},
      'adPlacements': [{'adPlacementRenderer': {'fixtureUrl': CDN+'?ad'}}],
      'adSlots': [{'fixture': True}], 'playerAds': [{'fixture': True}],
      'captions': {'fixture': 'preserve'}, 'important': True, 'companion': {'keep': True}}
CLEAN = {k:v for k,v in AD.items() if k not in ('adPlacements','adSlots','playerAds')}

class Playback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.clips = {}
        for name, shape in [('ad', '32x24'), ('content', '64x48')]:
            out = Path(cls.tmp.name)/(name+'.webm')
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'color=s={shape}:r=10:d=1','-c:v','libvpx','-threads','1',str(out)],check=True)
            cls.clips[name] = out.read_bytes()
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=os.getenv('CHROMIUM') or shutil.which('chromium'),args=['--no-sandbox','--disable-background-networking'])
        print('Fixture Chromium:', cls.browser.version, flush=True)
    @classmethod
    def tearDownClass(cls): cls.browser.close(); cls.pw.stop(); cls.tmp.cleanup()
    def setUp(self):
        self.ctx = self.browser.new_context(service_workers='block'); self.addCleanup(self.ctx.close)
        self.p = self.ctx.new_page(); self.p.set_content('<video muted playsinline></video>')
        self.p.evaluate("""([origin,cdn,clips])=>{
          window.fixtureMedia=[];
          window.fetch=async (path,init={})=>{
            const u=new URL(path,origin);let response;
            if(u.origin+u.pathname===cdn && init.method==='POST'){
              const kind=u.search.slice(1);if(!Object.hasOwn(clips,kind)) throw Error('unexpected clip');
              fixtureMedia.push(kind);
              response=new Response(Uint8Array.from(atob(clips[kind]),c=>c.charCodeAt(0)),{headers:{'content-type':'video/webm'}});
            }else if(u.origin===origin && ['/other','/youtubei/v1/player','/youtubei/v1/playerish','/bad'].includes(u.pathname)){
              response=new Response(u.pathname==='/bad'?'{':window.fixtureBody,{headers:{'content-type':'application/json; charset=utf-8'}});
            }else throw Error('unexpected fixture request');
            Object.defineProperty(response,'url',{value:u.href});return response;
          };
        }""", [ORIGIN,CDN,{k:base64.b64encode(v).decode() for k,v in self.clips.items()}])
        self.payload=AD
    @property
    def media(self):return self.p.evaluate('()=>fixtureMedia')
    @property
    def payload(self):return self._payload
    @payload.setter
    def payload(self,value):
        self._payload=value;self.p.evaluate('s=>{window.fixtureBody=s}',json.dumps(value))
    def gate(self,on=True): self.p.evaluate(GATE,[on,ORIGIN])
    def fetch(self,path='/youtubei/v1/player'): return self.p.evaluate("async p=>(await fetch(p,{method:'POST'})).json()",path)
    def play(self):
        return self.p.evaluate('''async () => {
          const p=await(await fetch('/youtubei/v1/player',{method:'POST'})).json();
          const seq=(p.adPlacements||[]).map(x=>x.adPlacementRenderer.fixtureUrl);
          seq.push(p.streamingData.adaptiveFormats[0].url);
          const sizes=[],v=document.querySelector('video');
          for(const url of seq){
            const b=await(await fetch(url,{method:'POST'})).blob();
            const local=URL.createObjectURL(b);v.src=local;
            const size=await new Promise((yes,no)=>{
              const t=setTimeout(()=>no(new Error('no decoded video frame')),5000);
              v.requestVideoFrameCallback((_,m)=>{clearTimeout(t);yes([m.width,m.height])});
              v.play().catch(no);
            });sizes.push(size);v.pause();v.removeAttribute('src');v.load();URL.revokeObjectURL(local);
          }return sizes}''')
    def test_ad_off_positive_control(self):
        self.gate(False); self.assertEqual(self.play(),[[32,24],[64,48]]); self.assertEqual(self.media,['ad','content'])
    def test_ad_on_content_first(self):
        self.gate(); self.assertEqual(self.play(),[[64,48]]); self.assertEqual(self.media,['content'])
    def test_clean_unchanged_decodes(self):
        self.payload=CLEAN; self.gate(); self.assertEqual(self.fetch(),CLEAN); self.assertEqual(self.play(),[[64,48]]); self.assertEqual(self.media,['content'])
    def test_scoped_response_fields(self):
        self.gate(); self.assertEqual(self.fetch('/youtubei/v1/player?prettyPrint=false'),CLEAN)
        for p in ['/other','/youtubei/v1/playerish']: self.assertEqual(self.fetch(p),AD)
    def test_direct_and_wrapped_parse(self):
        self.gate()
        for data,want in [(AD,CLEAN),({'playerResponse':AD,'sibling':AD},{'playerResponse':CLEAN,'sibling':AD})]:
            self.assertEqual(self.p.evaluate('s=>JSON.parse(s)',json.dumps(data)),want)
    def test_access_errors_and_lookalikes(self):
        self.gate()
        for data in [dict(AD,playabilityStatus={'status':'LOGIN_REQUIRED'}),dict(AD,streamingData={}),{'checkout':AD,'adSlots':['legitimate']},{'consent':True,'adPlacements':[]},dict(AD,videoDetails={}),{'playerResponse':{'adSlots':[]}}]:
            self.payload=data; self.assertEqual(self.fetch(),data)
        self.assertTrue(self.p.evaluate("async()=>{try{await(await fetch('/bad')).json();return false}catch(e){return e instanceof SyntaxError}}"))
    def test_reviver_and_unknown_formats(self):
        self.gate(); self.assertEqual(self.p.evaluate('s=>JSON.parse(s,(k,v)=>v)',json.dumps(AD)),AD)
        self.payload=dict(CLEAN,adSlots={'unexpected':'shape'}); self.assertEqual(self.fetch(),self.payload)
    def test_site_and_frame_scope(self):
        self.p.evaluate(GATE,[True,'https://other.example']); self.assertEqual(self.fetch(),AD)
        self.p.evaluate('()=>{let f=document.createElement("iframe");f.srcdoc="<!doctype html>";document.body.append(f)}')
        f=self.p.frames[-1]; f.wait_for_url('about:srcdoc'); f.evaluate(GATE,[True,ORIGIN]); self.assertEqual(f.evaluate('s=>JSON.parse(s)',json.dumps(AD)),AD)
    def test_response_metadata_gates(self):
        self.gate()
        for status,mime,redirected,url in [(403,'application/json',False,ORIGIN+'/youtubei/v1/player'),
                (200,'text/plain',False,ORIGIN+'/youtubei/v1/player'),(200,'application/json',True,ORIGIN+'/youtubei/v1/player'),
                (200,'application/json',False,'https://m.youtube.com.example/youtubei/v1/player'),(200,'application/json',False,'')]:
            got=self.p.evaluate("""async ([source,status,mime,redirected,url])=>{
              const r=new Response(source,{status,headers:{'content-type':mime}});
              Object.defineProperties(r,{url:{value:url},redirected:{value:redirected}});return r.json();
            }""",[json.dumps(AD),status,mime,redirected,url]);self.assertEqual(got,AD)
    def test_idempotence_and_disable(self):
        self.p.evaluate('()=>{window.original=JSON.parse;window.originalBody=Response.prototype.json}'); self.gate()
        self.p.evaluate('()=>{window.saved=JSON.parse;window.savedBody=Response.prototype.json}'); self.gate()
        self.assertTrue(self.p.evaluate('()=>saved===JSON.parse && savedBody===Response.prototype.json')); self.gate(False)
        self.assertTrue(self.p.evaluate('()=>JSON.parse===original&&Response.prototype.json===originalBody'))
        self.assertEqual(self.p.evaluate('s=>saved(s)',json.dumps(AD)),AD); self.assertEqual(self.fetch(),AD); self.gate(); self.assertEqual(self.fetch(),CLEAN)
    def test_does_not_overwrite_site_wrapper(self):
        self.gate(); self.p.evaluate('()=>{const p=JSON.parse;window.third=(...a)=>p(...a);JSON.parse=third}'); self.gate(False)
        self.assertTrue(self.p.evaluate('()=>JSON.parse===third')); self.assertEqual(self.p.evaluate('s=>third(s)',json.dumps(AD)),AD)
    def test_pending_read_respects_disable(self):
        self.gate(); self.p.evaluate('''async()=>{const r=await fetch('/youtubei/v1/player');window.start=()=>r.json()}''')
        self.assertEqual(self.p.evaluate("async ()=>{const p=start();const location={origin:'https://m.youtube.com'};("+JS+")(false,location.origin);return p}"),AD)

if __name__=='__main__': unittest.main(verbosity=2)
