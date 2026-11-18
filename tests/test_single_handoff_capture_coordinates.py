import gzip,json,hashlib,importlib.util,pathlib,tempfile,subprocess,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];HERE=ROOT/'experiments/single-handoff'
s=importlib.util.spec_from_file_location('capture',HERE/'capture_coordinates.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Coordinates(unittest.TestCase):
 def test_full_source_replay(self):
  f=json.loads(gzip.decompress((HERE/'fixtures/capture-coordinates.json.gz').read_bytes()))['files']
  for path,item in f.items():
   self.assertEqual(hashlib.sha256(item['source'].encode()).hexdigest(),item['sha256'])
   out=m.transform(path,item['source']);self.assertEqual(m.transform(path,out),out)
  out=m.transform(m.CAPTURE,f[m.CAPTURE]['source'])
  self.assertIn('+ (fullscreen ? topControlsHeight : 0)',out)
  spec=importlib.util.spec_from_file_location('diag',ROOT/'experiments/navigation-diagnostics/apply-capture.py');diag=importlib.util.module_from_spec(spec);spec.loader.exec_module(diag)
  # Existing numeric diagnostics remain independent; use module's exact transformation API.
  if hasattr(diag,'transform'):
   try:composed=diag.transform(f[m.CAPTURE]['source'])
   except TypeError:composed=diag.transform(m.CAPTURE,f[m.CAPTURE]['source'])
   self.assertIn('SANDIUM_CAPTURE_RING_V1',m.transform(m.CAPTURE,composed))
 def test_actual_owner_coordinate_contract(self):
  code='''import java.util.function.*;@interface Nullable {}
class Matrix {boolean identity=true;boolean isIdentity(){return identity;}}
class View {int w=1080,h=2234,top,left,sx,sy;boolean attached=true,layout;Matrix matrix=new Matrix();Object parent,params;int getWidth(){return w;}int getHeight(){return h;}int getTop(){return top;}int getLeft(){return left;}int getScrollX(){return sx;}int getScrollY(){return sy;}boolean isAttachedToWindow(){return attached;}boolean isLayoutRequested(){return layout;}Matrix getMatrix(){return matrix;}Object getParent(){return parent;}Object getLayoutParams(){return params;}}
class ViewGroup extends View {int pt,pl;int getPaddingTop(){return pt;}int getPaddingLeft(){return pl;}static class MarginLayoutParams {int topMargin,leftMargin;}}
interface NativePage {'''+m.API+'''default int getHeightOverlappedWithTopControls(){return 0;}}
class FeedSurfaceCoordinator {boolean wrapper;boolean hasSandiumWallpaperRoot(){return wrapper;}}
class Tab {Object page;boolean privateTab;Object getNativePage(){return page;}boolean isIncognitoBranded(){return privateTab;}}
class Controls {int content,top,topOffset,bottomOffset,bottom=168;int getContentOffset(){return content;}int getTopControlsHeight(){return top;}int getTopControlOffset(){return topOffset;}int getBottomControlOffset(){return bottomOffset;}int getBottomControlsHeight(){return bottom;}}
class Page implements NativePage {boolean mIsDestroyed;Tab mTab=new Tab();Object mFeedSurfaceProvider;View root=new View();int mToolbarHeight=168;Supplier<Integer> mTabStripHeightSupplier=()->0;Controls mBrowserControlsStateProvider=new Controls();View getView(){return root;}public int getHeightOverlappedWithTopControls(){return mBrowserControlsStateProvider.top;}
'''+m.OWNER+'''
Page(){mTab.page=this;root.parent=new ViewGroup();root.params=new ViewGroup.MarginLayoutParams();layout(0);}void layout(int content){mBrowserControlsStateProvider.content=content;root.top=content-mToolbarHeight-mTabStripHeightSupplier.get();((ViewGroup.MarginLayoutParams)root.params).topMargin=root.top;}}
public class Harness {static int sandiumCaptureOverlap(NativePage page){Integer owned=page.getSandiumCaptureTopOverlap();return owned!=null?owned:page.getHeightOverlappedWithTopControls();}
static void check(boolean b){if(!b)throw new AssertionError();}static void compare(Page p,int windowInset,int localY,int syncHeight){int overlap=sandiumCaptureOverlap(p);int live=windowInset+p.root.top+localY;int bitmap=localY-overlap+syncHeight;int replay=windowInset+p.mBrowserControlsStateProvider.content+bitmap-syncHeight;check(live==replay);}
public static void main(String[]args){Page p=new Page();check(p.getSandiumCaptureTopOverlap()==168);compare(p,120,300,0);compare(p,120,300,168);p.mBrowserControlsStateProvider.top=168;p.layout(168);compare(p,0,300,168);compare(p,120,300,0);p.layout(50);compare(p,120,300,168);p.mTabStripHeightSupplier=()->48;p.mBrowserControlsStateProvider.top=216;p.layout(50);compare(p,84,300,216);check(p.getSandiumCaptureTopOverlap()==null);p.mTabStripHeightSupplier=()->0;p.mBrowserControlsStateProvider.top=0;p.layout(0);compare(p,0,300,0);
FeedSurfaceCoordinator wrapper=new FeedSurfaceCoordinator();wrapper.wrapper=true;p.mFeedSurfaceProvider=wrapper;check(p.getSandiumCaptureTopOverlap()==null&&sandiumCaptureOverlap(p)==0);p.mFeedSurfaceProvider=null;
p.root.attached=false;check(p.getSandiumCaptureTopOverlap()==null);p.root.attached=true;p.root.layout=true;check(p.getSandiumCaptureTopOverlap()==null);p.root.layout=false;p.root.matrix.identity=false;check(p.getSandiumCaptureTopOverlap()==null);p.root.matrix.identity=true;p.root.top++;check(p.getSandiumCaptureTopOverlap()==null);p.layout(0);p.mTab.page=new Object();check(p.getSandiumCaptureTopOverlap()==null);p.mTab.page=p;p.mTab.privateTab=true;check(p.getSandiumCaptureTopOverlap()==null);p.mTab.privateTab=false;((ViewGroup)p.root.parent).pt=120;check(p.getSandiumCaptureTopOverlap()==null);((ViewGroup)p.root.parent).pt=0;p.mIsDestroyed=true;check(p.getSandiumCaptureTopOverlap()==null);System.out.println("CAPTURE_COORDINATES=PASS");}}
'''
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'Harness.java';p.write_text(code)
   r=subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-d',d,str(p)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   r=subprocess.run(['java','-cp',d,'Harness'],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);self.assertIn('CAPTURE_COORDINATES=PASS',r.stdout)
 def test_actual_recording_and_result_lifetime(self):
  f=json.loads(gzip.decompress((HERE/'fixtures/capture-coordinates.json.gz').read_bytes()))['files']
  out=m.transform(m.CAPTURE,f[m.CAPTURE]['source'])
  a=out.index('                            recordingValid[0] = snapshot.matchesRecording(tab);');b=out.index('canvas.translate(0, -snapshot.overlap);',a)+len('canvas.translate(0, -snapshot.overlap);');start=out[a:b]
  a=out.index('                    resultCapture -> {')+len('                    resultCapture -> {');depth=1;b=a
  while depth:
   if out[b]=='{':depth+=1
   elif out[b]=='}':depth-=1
   b+=1
  delivery=out[a:b-1]
  files={
   'android/graphics/Matrix.java':'package android.graphics;public class Matrix {public int value;public Matrix(){}public Matrix(Matrix m){value=m.value;}public boolean equals(Object m){return m instanceof Matrix&&((Matrix)m).value==value;}}',
   'android/view/View.java':'''package android.view;public class View {public int width=100,height=200,top,left,sx,sy,windowY;public boolean attached=true;public boolean isAttachedToWindow(){return attached;}public void getLocationInWindow(int[] xy){xy[0]=0;xy[1]=windowY;}public Object parent=new Object();public android.graphics.Matrix matrix=new android.graphics.Matrix();public int getWidth(){return width;}public int getHeight(){return height;}public int getTop(){return top;}public int getLeft(){return left;}public int getScrollX(){return sx;}public int getScrollY(){return sy;}public Object getParent(){return parent;}public android.graphics.Matrix getMatrix(){return matrix;}}''',
   'org/chromium/content_public/browser/WebContents.java':'''package org.chromium.content_public.browser;import android.view.View;public class WebContents {public boolean dead;public Delegate delegate=new Delegate();public boolean isDestroyed(){return dead;}public Delegate getViewAndroidDelegate(){return delegate;}public static class Delegate {public View container=new View();public View getContainerView(){return container;}}}''',
   'Harness.java':'''import android.view.View;@interface Nullable {}
class NativePage {Integer owned=168;int background=12;Integer getSandiumCaptureTopOverlap(){return owned;}int getHeightOverlappedWithTopControls(){return 0;}int getBackgroundColor(){return background;}}
class Tab {NativePage page=new NativePage();View view=new View();org.chromium.content_public.browser.WebContents contents=new org.chromium.content_public.browser.WebContents();org.chromium.content_public.browser.WebContents getWebContents(){return contents;}NativePage getNativePage(){return page;}View getView(){return view;}}
class Canvas {int color,dy;boolean clipped;void clipRect(int a,int b,int c,int d){clipped=true;}void drawColor(int c){color=c;}void translate(int x,int y){dy=y;}}
class Bitmap {int recycles;void recycle(){recycles++;}}
class Buffer {int closes;boolean fail;void close(){closes++;if(fail)throw new IllegalStateException();}}
class CaptureResult {static class Destination{static final int BITMAP=0,HARDWARE_BUFFER=1;}Bitmap bitmap=new Bitmap();Buffer buffer=new Buffer();int releases;Bitmap getBitmap(){return bitmap;}Buffer getHardwareBuffer(){return buffer;}Runnable getReleaseCallback(){return ()->releases++;}}
class Callback {int calls,nulls;CaptureResult result;void onResult(CaptureResult r){calls++;if(r==null)nulls++;result=r;}}
public class Harness {static <T>T assumeNonNull(T x){if(x==null)throw new IllegalStateException();return x;}
'''+m.SNAPSHOT+'''
Tab tab=new Tab();SandiumCaptureSnapshot snapshot=new SandiumCaptureSnapshot(tab);boolean[] recordingValid={true};Callback callback=new Callback();int destination=1;
void start(Canvas canvas){'''+start+'''}
void end(){recordingValid[0]&=snapshot.matchesRecording(tab);}
void deliver(CaptureResult resultCapture){'''+delivery+'''}
static void check(boolean b){if(!b)throw new AssertionError();}
public static void main(String[]a){Harness h=new Harness();Canvas canvas=new Canvas();h.start(canvas);check(canvas.color==12&&canvas.dy==-168);h.end();h.tab.page=new NativePage();CaptureResult result=new CaptureResult();h.deliver(result);check(h.callback.result==result&&result.buffer.closes==0); // ordinary departure after synchronous recording is valid.
h=new Harness();h.start(new Canvas());h.tab.view.top=2;h.end();result=new CaptureResult();h.deliver(result);check(h.callback.nulls==1&&result.buffer.closes==1&&result.releases==1);
h=new Harness();h.tab.page=new NativePage();canvas=new Canvas();h.start(canvas);check(canvas.clipped);h.end();h.destination=0;result=new CaptureResult();h.deliver(result);check(h.callback.nulls==1&&result.bitmap.recycles==1);
h=new Harness();h.start(new Canvas());h.tab.view.matrix.value=3;h.end();result=new CaptureResult();result.buffer.fail=true;try{h.deliver(result);throw new AssertionError();}catch(IllegalStateException expected){}check(result.releases==1&&h.callback.nulls==1);
h=new Harness();h.start(new Canvas());h.tab.contents.delegate.container.height++;h.end();result=new CaptureResult();h.deliver(result);check(h.callback.nulls==1&&result.buffer.closes==1);
h=new Harness();h.start(new Canvas());h.tab.contents=new org.chromium.content_public.browser.WebContents();h.end();result=new CaptureResult();h.deliver(result);check(h.callback.nulls==1&&result.buffer.closes==1);
h=new Harness();h.start(new Canvas());h.tab.view.attached=false;h.end();result=new CaptureResult();h.deliver(result);check(h.callback.nulls==1);
h=new Harness();h.start(new Canvas());h.tab.view.windowY++;h.end();result=new CaptureResult();h.deliver(result);check(h.callback.nulls==1);
System.out.println("CAPTURE_LIFETIME=PASS");}}
'''}
  with tempfile.TemporaryDirectory() as d:
   paths=[]
   for p,text in files.items():
    q=pathlib.Path(d)/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(text);paths.append(str(q))
   r=subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-d',d]+paths,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   r=subprocess.run(['java','-cp',d,'Harness'],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);self.assertIn('CAPTURE_LIFETIME=PASS',r.stdout)
