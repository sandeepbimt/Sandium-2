import gzip,json,hashlib,importlib.util,pathlib,tempfile,subprocess,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];HERE=ROOT/'experiments/single-handoff'
s=importlib.util.spec_from_file_location('wallpaper',HERE/'wallpaper_admission.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Wallpaper(unittest.TestCase):
 def test_pinned_worker_size_contract(self):
  f=json.loads(gzip.decompress((HERE/'fixtures/wallpaper-worker-api.json.gz').read_bytes()))
  for item in f['files'].values():self.assertEqual(hashlib.sha256(item['source'].encode()).hexdigest(),item['sha256'])
  worker=next(v['source'] for p,v in f['files'].items() if p.endswith('FetchWallpaperWorkerTask.java'))
  crop=next(v['source'] for p,v in f['files'].items() if p.endswith('NTPImageUtil.java'))
  gradient=next(v['source'] for p,v in f['files'].items() if p.endswith('ImageUtils.java'))
  self.assertIn('NTPImageUtil.getWallpaperBitmap(mNTPImage, mLayoutWidth, mLayoutHeight)',worker)
  self.assertIn('layoutWidth, (int) layoutHeight);',crop)
  self.assertIn('bitmapWithGradient = ImageUtils.addGradient(newBitmap);',crop)
  self.assertIn('int w = src.getWidth();',gradient);self.assertIn('int h = src.getHeight();',gradient)
  self.assertIn('Bitmap result = Bitmap.createBitmap(src,0,0,w,h);',gradient)
 def test_complete_pipeline_source(self):
  f=json.loads(gzip.decompress((HERE/'fixtures/wallpaper-admission.json.gz').read_bytes()))['files'][m.PATH]
  self.assertEqual(hashlib.sha256(f['source'].encode()).hexdigest(),f['sha256'])
  out=m.transform(f['source']);self.assertEqual(m.transform(out),out)
  self.assertIn('mWallpaperRetrievedCallback.bgWallpaperRetrieved(bitmap);',out)
  self.assertIn('mSandiumWallpaperCoordinator.onSandiumWallpaperBitmapChanged();',out)
  self.assertIn('private void setBackgroundImage(NTPImage ntpImage)',out)
  for hook in ('mSandiumWallpaperReleased = true;','mSandiumWallpaperSuspended = true;','mSandiumWallpaperSuspended = false;'):
   with self.assertRaises(ValueError):m.transform(out.replace(hook,''))
  for hook in ('mSandiumWallpaperReleased = true;\n        cancelSandiumWallpaperRequest();',
               'mSandiumWallpaperSuspended = true;\n        if (mSandiumWallpaperCoordinator != null) cancelSandiumWallpaperRequest();'):
   with self.assertRaises(ValueError):m.transform(out.replace(hook,hook.replace('cancelSandiumWallpaperRequest();','')))
  # Legacy non-backed/sheet branch stays intact, including its original MATRIX policy.
  self.assertIn('mBgImageView.setScaleType(ImageView.ScaleType.MATRIX);',out)
 def test_generation_negative_mutation(self):
  original=m.METHODS
  try:
   m.METHODS=original.replace('mSandiumWallpaperRequest == request && ', '')
   with self.assertRaises(AssertionError) as caught:self.test_actual_request_methods()
   self.assertIn('java.lang.AssertionError',str(caught.exception))
  finally:m.METHODS=original
 def test_view_mutation_negative(self):
  original=m.METHODS
  try:
   m.METHODS=original.replace('            if (!isSandiumWallpaperSelectionCurrent(revision, image, target)) return;', '',1)
   with self.assertRaises(AssertionError) as caught:self.test_actual_request_methods()
   self.assertIn('java.lang.AssertionError',str(caught.exception))
  finally:m.METHODS=original
 def test_actual_request_methods(self):
  code='''import java.util.*;import java.util.concurrent.Executor;
@java.lang.annotation.Target({java.lang.annotation.ElementType.TYPE_USE}) @java.lang.annotation.Retention(java.lang.annotation.RetentionPolicy.CLASS) @interface Nullable {}
class NTPImage {} class Wallpaper extends NTPImage {boolean rich;boolean isRichMedia(){return rich;}}
class Bitmap {int w,h;boolean recycled;Bitmap(int w,int h){this.w=w;this.h=h;}int getWidth(){return w;}int getHeight(){return h;}boolean isRecycled(){return recycled;}}
class ViewTreeObserver {interface OnGlobalLayoutListener {void onGlobalLayout();}boolean alive=true;List<OnGlobalLayoutListener> listeners=new ArrayList<>();boolean isAlive(){return alive;}void addOnGlobalLayoutListener(OnGlobalLayoutListener l){listeners.add(l);}void removeOnGlobalLayoutListener(OnGlobalLayoutListener l){listeners.remove(l);}void layout(){for(var l:List.copyOf(listeners))l.onGlobalLayout();}}
class ImageView {enum ScaleType{MATRIX}int w,h,clears;Runnable onScale,onClear;ViewTreeObserver observer=new ViewTreeObserver();int getMeasuredWidth(){return w;}int getMeasuredHeight(){return h;}ViewTreeObserver getViewTreeObserver(){return observer;}void setScaleType(ScaleType s){if(onScale!=null){Runnable r=onScale;onScale=null;r.run();}}void setImageDrawable(Object x){if(x!=null)throw new AssertionError();clears++;if(onClear!=null){Runnable r=onClear;onClear=null;r.run();}}}
class AsyncTask {static final Object THREAD_POOL_EXECUTOR=new Object();}
class FetchWallpaperWorkerTask {interface WallpaperRetrievedCallback {void bgWallpaperRetrieved(Bitmap b);void logoRetrieved(Wallpaper w,Bitmap b);}static List<FetchWallpaperWorkerTask> tasks=new ArrayList<>();NTPImage image;int width,height;boolean cancelled;Runnable onCancel;WallpaperRetrievedCallback callback;FetchWallpaperWorkerTask(NTPImage i,int w,int h,WallpaperRetrievedCallback c){image=i;width=w;height=h;callback=c;}void executeOnExecutor(Object e){tasks.add(this);}void cancel(boolean b){cancelled=true;if(onCancel!=null){Runnable r=onCancel;onCancel=null;r.run();}}}
class Activity {boolean dead;boolean isFinishing(){return dead;}boolean isDestroyed(){return dead;}}
class Prefs {boolean enabled=true;boolean getBoolean(Object k){return enabled;}}
class UserPrefs {static Prefs prefs=new Prefs();static Prefs get(Object p){return prefs;}}
class BravePref {static final Object NEW_TAB_PAGE_SHOW_BACKGROUND_IMAGE=new Object();}
class NTPImageUtil {static boolean feature=true;static boolean shouldEnableNTPFeature(){return feature;}}
class Coordinator {int changes;Runnable callback;void onSandiumWallpaperBitmapChanged(){changes++;if(callback!=null){Runnable r=callback;callback=null;r.run();}}}
public class Harness {Coordinator mSandiumWallpaperCoordinator=new Coordinator();Object mProfile=new Object(),mSponsoredTab=new Object();NTPImage mNtpImageGlobal=new NTPImage();ImageView mBgImageView=new ImageView();Activity mActivity=new Activity();FetchWallpaperWorkerTask mWorkerTask;int bitmapCalls,logoCalls;Runnable onBitmap;
FetchWallpaperWorkerTask.WallpaperRetrievedCallback mWallpaperRetrievedCallback=new FetchWallpaperWorkerTask.WallpaperRetrievedCallback(){public void bgWallpaperRetrieved(Bitmap b){bitmapCalls++;if(onBitmap!=null){Runnable r=onBitmap;onBitmap=null;r.run();}}public void logoRetrieved(Wallpaper w,Bitmap b){logoCalls++;}};
'''+m.FIELDS+m.METHODS+'''
static void check(boolean b){if(!b)throw new AssertionError();}static FetchWallpaperWorkerTask latest(){var ts=FetchWallpaperWorkerTask.tasks;return ts.get(ts.size()-1);}void select(NTPImage image){mNtpImageGlobal=image;selectSandiumWallpaper(image);}static Harness measured(){Harness h=new Harness();h.mBgImageView.w=300;h.mBgImageView.h=600;return h;}
public static void main(String[]args){
 Harness h=measured();int n=FetchWallpaperWorkerTask.tasks.size();NTPImage first=h.mNtpImageGlobal;h.select(first);check(FetchWallpaperWorkerTask.tasks.size()==n+1);var old=latest();check(old.image==first);h.mBgImageView.observer.layout();check(FetchWallpaperWorkerTask.tasks.size()==n+1);h.select(first);check(FetchWallpaperWorkerTask.tasks.size()==n+1);
 NTPImage second=new NTPImage();h.select(second);check(FetchWallpaperWorkerTask.tasks.size()==n+2&&old.cancelled&&latest().image==second);old.callback.bgWallpaperRetrieved(new Bitmap(300,600));check(h.bitmapCalls==0);var current=latest();current.callback.bgWallpaperRetrieved(new Bitmap(300,600));check(h.bitmapCalls==1);
 h.mBgImageView.w=400;current.callback.bgWallpaperRetrieved(new Bitmap(300,600));check(h.bitmapCalls==1);h.mBgImageView.observer.layout();check(latest().width==400);latest().callback.bgWallpaperRetrieved(new Bitmap(399,600));check(h.bitmapCalls==1);latest().callback.bgWallpaperRetrieved(new Bitmap(400,600));check(h.bitmapCalls==2);h.mBgImageView.w=300;current.callback.bgWallpaperRetrieved(new Bitmap(300,600));check(h.bitmapCalls==2);h.mBgImageView.w=400;
 var pending=latest();h.cancelSandiumWallpaperRequest();check(h.mBgImageView.observer.listeners.isEmpty());pending.callback.bgWallpaperRetrieved(new Bitmap(400,600));check(h.bitmapCalls==2);
 h=measured();h.select(h.mNtpImageGlobal);current=latest();UserPrefs.prefs.enabled=false;current.callback.bgWallpaperRetrieved(new Bitmap(300,600));check(h.bitmapCalls==0);h.select(h.mNtpImageGlobal);check(h.mSandiumWallpaperRequest==null);UserPrefs.prefs.enabled=true;h.select(h.mNtpImageGlobal);check(latest()!=current);
 Harness unmeasured=new Harness();n=FetchWallpaperWorkerTask.tasks.size();unmeasured.select(unmeasured.mNtpImageGlobal);check(FetchWallpaperWorkerTask.tasks.size()==n);unmeasured.mBgImageView.w=50;unmeasured.mBgImageView.h=70;unmeasured.mBgImageView.observer.layout();check(FetchWallpaperWorkerTask.tasks.size()==n+1);
 Harness changing=measured();changing.select(changing.mNtpImageGlobal);var before=latest();changing.onBitmap=()->changing.select(new NTPImage());before.callback.bgWallpaperRetrieved(new Bitmap(300,600));before.callback.logoRetrieved(new Wallpaper(),new Bitmap(4,4));check(changing.bitmapCalls==1&&changing.logoCalls==0);
 Harness reentrant=measured();reentrant.mSandiumWallpaperCoordinator.callback=()->{reentrant.cancelSandiumWallpaperRequest();reentrant.mSandiumWallpaperCoordinator=null;};n=FetchWallpaperWorkerTask.tasks.size();reentrant.select(reentrant.mNtpImageGlobal);check(FetchWallpaperWorkerTask.tasks.size()==n);
 Harness destroyed=measured();destroyed.select(destroyed.mNtpImageGlobal);destroyed.mActivity.dead=true;latest().callback.bgWallpaperRetrieved(new Bitmap(300,600));check(destroyed.bitmapCalls==0);
 Harness replacement=measured();replacement.select(replacement.mNtpImageGlobal);var beforeView=latest();ImageView oldView=replacement.mBgImageView;replacement.mBgImageView=new ImageView();replacement.mBgImageView.w=300;replacement.mBgImageView.h=600;replacement.select(replacement.mNtpImageGlobal);check(oldView.observer.listeners.isEmpty());beforeView.callback.bgWallpaperRetrieved(new Bitmap(300,600));check(replacement.bitmapCalls==0);latest().callback.bgWallpaperRetrieved(new Bitmap(300,600));check(replacement.bitmapCalls==1);
 for(boolean scale:new boolean[]{false,true}){Harness viewReentry=measured();NTPImage newer=new NTPImage();Runnable change=()->viewReentry.select(newer);if(scale)viewReentry.mBgImageView.onScale=change;else viewReentry.mBgImageView.onClear=change;viewReentry.select(viewReentry.mNtpImageGlobal);check(latest().image==newer);check(viewReentry.mSandiumRequestedWallpaper==newer);check(viewReentry.mSandiumWallpaperCoordinator.changes==1);check(viewReentry.mBgImageView.clears==(scale?1:2));}
 Harness cancelReentry=measured();cancelReentry.select(cancelReentry.mNtpImageGlobal);var cancelOld=latest();NTPImage finalImage=new NTPImage();cancelOld.onCancel=()->cancelReentry.select(finalImage);cancelReentry.select(new NTPImage());check(cancelReentry.mSandiumRequestedWallpaper==finalImage&&latest().image==finalImage);
 Harness lifecycle=measured();lifecycle.select(lifecycle.mNtpImageGlobal);lifecycle.mSandiumWallpaperSuspended=true;lifecycle.cancelSandiumWallpaperRequest();n=FetchWallpaperWorkerTask.tasks.size();lifecycle.select(new NTPImage());check(FetchWallpaperWorkerTask.tasks.size()==n);lifecycle.mSandiumWallpaperSuspended=false;lifecycle.select(lifecycle.mNtpImageGlobal);check(FetchWallpaperWorkerTask.tasks.size()==n+1);lifecycle.mSandiumWallpaperReleased=true;lifecycle.cancelSandiumWallpaperRequest();lifecycle.select(new NTPImage());check(FetchWallpaperWorkerTask.tasks.size()==n+1);
 Harness profileSwap=measured();profileSwap.select(profileSwap.mNtpImageGlobal);profileSwap.mProfile=new Object();latest().callback.bgWallpaperRetrieved(new Bitmap(300,600));check(profileSwap.bitmapCalls==0);var previousProfileTask=latest();n=FetchWallpaperWorkerTask.tasks.size();profileSwap.mBgImageView.w=301;profileSwap.mBgImageView.observer.layout();check(FetchWallpaperWorkerTask.tasks.size()==n);profileSwap.mBgImageView.w=300;profileSwap.select(profileSwap.mNtpImageGlobal);check(latest()!=previousProfileTask);latest().callback.bgWallpaperRetrieved(new Bitmap(300,600));check(profileSwap.bitmapCalls==1);
 System.out.println("WALLPAPER_OWNER=PASS");}}
'''
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'Harness.java';p.write_text(code)
   r=subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-d',d,str(p)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   r=subprocess.run(['java','-cp',d,'Harness'],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);self.assertIn('WALLPAPER_OWNER=PASS',r.stdout)
