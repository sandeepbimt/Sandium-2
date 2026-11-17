#!/usr/bin/env python3
"""Execute production Java crop/worker code with tiny Android stubs (not device QA)."""
import os, pathlib, subprocess, tempfile, shutil
repo=pathlib.Path(__file__).resolve().parents[2]
source=(repo/'android/java/org/chromium/chrome/browser/suggestions/mostvisited/SandiumHomeShortcuts.java').read_text()
# Compile the actual production block, not a second implementation of the algorithm.
block=source[source.index('    private java.util.concurrent.ThreadPoolExecutor mIconWorker;'):source.index('    private final Runnable mRender')]
assert 'icon.setImageBitmap(bitmap); letter.setVisibility(GONE);\n                normalizeIcon' in source
assert 'cancelIconWork();' in source[source.index('private void updateVisibility'):source.index('private void stopWiggles')]
assert 'cancelIconWork();' in source[source.index('private void render()'):source.index('private void updateWiggles')]
assert 'cancelIconWork();' in source[source.index('onDetachedFromWindow()'):source.index('onWindowVisibilityChanged')]
with tempfile.TemporaryDirectory() as td:
 d=pathlib.Path(td)
 files={
 'android/os/Process.java': 'package android.os; public class Process { public static final int THREAD_PRIORITY_BACKGROUND=10; public static void setThreadPriority(int p) {} }',
 'android/graphics/Bitmap.java': '''package android.graphics;
 public class Bitmap {
 public final int w,h; public final int[] p; public volatile boolean fail; public java.util.concurrent.CountDownLatch hold;
 public Bitmap(int w,int h,int[] p){this.w=w;this.h=h;this.p=p;}
 public int getWidth(){return w;} public int getHeight(){return h;}
 public void getPixels(int[] dst,int off,int stride,int x,int y,int width,int height){
 if(Thread.currentThread().getName().equals("main"))throw new AssertionError("UI scan");
 if(fail)throw new IllegalStateException();
 if(hold!=null)try {hold.await();}catch(InterruptedException e){Thread.currentThread().interrupt();return;}
 System.arraycopy(p,0,dst,0,p.length);}
 public static Bitmap createBitmap(Bitmap b,int x,int y,int w,int h){return new Bitmap(w,h,new int[w*h]);}
 }''',
 'Harness.java': '''import java.util.*; import java.util.concurrent.*;
 public class Harness {
 static final int VISIBLE=0; int mGeneration; boolean attached=true,shown=true;
 ConcurrentLinkedQueue<Runnable> posted=new ConcurrentLinkedQueue<>();
 boolean isAttachedToWindow(){return attached;} boolean isShown(){return shown;} int getWindowVisibility(){return shown?0:8;}
 boolean post(Runnable r){posted.add(r);return true;}
 static class ImageView { android.graphics.Bitmap image; boolean attached=true; int updates;
 boolean isAttachedToWindow(){return attached;} void setImageBitmap(android.graphics.Bitmap b){image=b;updates++;}}
 '''+block+'''
 static void check(boolean yes){if(!yes)throw new AssertionError();}
 static int[] art(int bg,int padding){int[] p=new int[64*64];Arrays.fill(p,bg);for(int y=padding;y<64-padding;y++)for(int x=padding;x<64-padding;x++)p[y*64+x]=0xff123456;return p;}
 void drain()throws Exception {if(mIconWorker!=null){mIconWorker.shutdown();check(mIconWorker.awaitTermination(3,TimeUnit.SECONDS));} Runnable r;while((r=posted.poll())!=null)r.run();}
 public static void main(String[] args)throws Exception{
 for(int bg:new int[]{0,0xffffffff,0xff000000}){
 int[] p=art(bg,12), before=p.clone();int[] b=ArtworkPadding.bounds(p,64,64);check(b!=null && b[0]<=10 && b[1]<=10 && b[2]>=46 && b[3]>=46);check(Arrays.equals(p,before));
 for(int y=0;y<64;y++)for(int x=0;x<64;x++)if(p[y*64+x]==0xff123456)check(x>=b[0]+2&&x<b[0]+b[2]-2&&y>=b[1]+2&&y<b[1]+b[3]-2);
 }
 check(ArtworkPadding.bounds(art(0,0),64,64)==null);
 check(ArtworkPadding.bounds(art(0xffaa0000,12),64,64)==null);
 int[] marked=art(0,12);marked[0]=0xff123456;check(ArtworkPadding.bounds(marked,64,64)==null);
 check(ArtworkPadding.bounds(new int[4096],64,64)==null);
 check(ArtworkPadding.bounds(new int[64],8,8)==null);
 check(ArtworkPadding.bounds(new int[513*513],513,513)==null);
 int[] asymmetric=art(0,12);asymmetric[32*64+3]=0xff123456;check(ArtworkPadding.bounds(asymmetric,64,64)==null);
 Thread.currentThread().interrupt();check(ArtworkPadding.bounds(art(0,12),64,64)==null);Thread.interrupted();
 android.graphics.Bitmap original=new android.graphics.Bitmap(64,64,art(0,12));
 Harness host=new Harness();ImageView image=new ImageView();image.setImageBitmap(original);host.normalizeIcon(original,image,host.mGeneration);host.drain();check(image.updates==2 && image.image!=original);host.cancelIconWork();
 for(int mode=0;mode<4;mode++){
 host=new Harness();image=new ImageView();image.setImageBitmap(original);host.normalizeIcon(original,image,0);
 if(mode==0)host.cancelIconWork();if(mode==1)host.attached=false;if(mode==2)host.shown=false;if(mode==3)image.attached=false;
 host.drain();check(image.updates==1);host.cancelIconWork();}
 // A removal/reorder invalidates even an already posted completion; no wrong tile refill.
 host=new Harness();image=new ImageView();image.setImageBitmap(original);host.normalizeIcon(original,image,0);
 host.mIconWorker.shutdown();check(host.mIconWorker.awaitTermination(3,TimeUnit.SECONDS));
 host.cancelIconWork();android.graphics.Bitmap replacement=new android.graphics.Bitmap(64,64,art(0xffffffff,8));image.setImageBitmap(replacement);
 host.drain();check(image.image==replacement && image.updates==2);
 host=new Harness();host.shown=false;image=new ImageView();host.normalizeIcon(original,image,0);check(host.mIconWorker==null);
 host=new Harness();image=new ImageView();original.fail=true;image.setImageBitmap(original);host.normalizeIcon(original,image,0);host.drain();check(image.image==original && image.updates==1);host.cancelIconWork();original.fail=false;
 host=new Harness();original.hold=new CountDownLatch(1);image=new ImageView();image.setImageBitmap(original);host.normalizeIcon(original,image,0);
 for(int n=0;n<40;n++)host.normalizeIcon(original,image,0);
 check(host.mIconWorker.getQueue().size()<=25);check(image.image==original);host.cancelIconWork();original.hold.countDown();host.drain();check(image.updates==1);
 System.out.println("PASS production crop edge cases, immutable fallback, background worker, bounded queue, cancellation and stale completion guards");
 }
 }'''}
 for name,text in files.items():
  p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
 javac=shutil.which('javac')
 command=[javac,'-d',str(d)] if javac else ['java','-jar',os.environ['ECJ_JAR'],'-17','-d',str(d)]
 subprocess.run(command+[str(p) for p in d.rglob('*.java')],check=True)
 subprocess.run(['java','-cp',str(d),'Harness'],check=True,timeout=15)
