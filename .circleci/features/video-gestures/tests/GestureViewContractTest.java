import android.content.Context;
import android.view.MotionEvent;
import org.chromium.chrome.browser.sandium.video.*;
public class GestureViewContractTest {
    static int checks;
    static void check(boolean b) { checks++; if (!b) throw new AssertionError("check " + checks); }
    static class Host implements SandiumVideoGestureView.Host {
        long gen; boolean eligible=true, seekable=true; int actions, begins, previews, clears;
        public boolean isEligible(){return eligible;} public long generation(){return gen;}
        public boolean canSeek(){return seekable;} public void togglePlayback(){actions++;}
        public void seekBy(long x){actions++;} public void beginAdjustment(){begins++;}
        public void preview(SandiumVideoGestureState.Kind k,double x){previews++;}
        public void adjustBrightness(double x){actions++;} public void adjustVolume(double x){actions++;}
        public void clearPreview(){clears++;}
    }
    static void event(SandiumVideoGestureView v,int a,float x,float y,long t,int n){v.onTouchEvent(new MotionEvent(a,x,y,t,n));}
    static void down(SandiumVideoGestureView v){event(v,0,500,250,0,1);}
    static void up(SandiumVideoGestureView v){event(v,1,500,250,100,1);}
    public static void main(String[] args) throws Exception {
        var h = new Host(); var v = new SandiumVideoGestureView(new Context(),h);
        down(v); up(v); check(h.actions==1 && h.begins==1);
        up(v); check(h.actions==1); // exactly one dispatch
        down(v); h.gen++; up(v); check(h.actions==1);
        down(v); event(v,3,500,250,20,1); up(v); check(h.actions==1);
        down(v); event(v,5,500,250,20,2); up(v); check(h.actions==1);
        down(v); h.eligible=false; up(v); check(h.actions==1); h.eligible=true;
        down(v); event(v,2,600,250,50,1); check(h.actions==1 && h.previews>0);
        event(v,1,600,250,100,1); check(h.actions==2);
        down(v); event(v,2,600,250,50,1); h.seekable=false; event(v,1,600,250,100,1); check(h.actions==2);
        h.seekable=true;
        down(v); var resize = SandiumVideoGestureView.class.getDeclaredMethod("onSizeChanged",int.class,int.class,int.class,int.class);
        resize.setAccessible(true); resize.invoke(v,500,1000,1000,500); up(v); check(h.actions==2);
        down(v); var detach = SandiumVideoGestureView.class.getDeclaredMethod("onDetachedFromWindow");
        detach.setAccessible(true); detach.invoke(v); up(v); check(h.actions==2);
        System.out.println(checks+" view contract checks passed against minimal test doubles (not Android runtime)");
    }
}
