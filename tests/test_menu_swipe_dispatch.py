"""Execute production dispatch/replay and hit eligibility with narrow Android API doubles.
Not an Android runtime/touch-routing integration test.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
S = (ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()

class MenuSwipeDispatch(unittest.TestCase):
    def test_exact_dispatch_replay_and_overflow_exclusion(self):
        dispatch = S[S.index('    @Override public boolean dispatchTouchEvent(MotionEvent event) {'):S.index('    @Override public boolean dispatchKeyEvent')]
        eligibility = S[S.index('    private boolean insidePageGestureArea'):S.index('    @Override public boolean onInterceptTouchEvent')]
        source = '''import java.util.*;
class MotionEvent {
 static final int ACTION_DOWN=0,ACTION_UP=1,ACTION_MOVE=2,ACTION_CANCEL=3,ACTION_POINTER_DOWN=5,ACTION_POINTER_UP=6;
 int action; float x,y; MotionEvent(int a,float xx,float yy){action=a;x=xx;y=yy;}
 int getActionMasked(){return action;} float getX(){return x;} float getY(){return y;}
 static MotionEvent obtain(MotionEvent e){return new MotionEvent(e.action,e.x,e.y);}
 void setAction(int a){action=a;} void recycle(){}
}
class Base {
 boolean dispatchTouchEvent(MotionEvent e){return true;}
}
public class DispatchTest extends Base {
 static class View {
  boolean shown=true, overflow; int bottom=100;
  boolean isShown(){return shown;}
  boolean getLocalVisibleRect(android.graphics.Rect r){r.left=0;r.right=100;r.top=0;r.bottom=bottom;return shown;}
  boolean canScrollHorizontally(int d){return overflow;}
 }
 static class Delegate { int cancels; boolean onTouchEvent(MotionEvent e){if(e.action==3)cancels++;return true;} }
 boolean mPagerSequenceOwned,mPagerDragReplay,mAllMenu;
 Object mDraft; View mPageGestureArea=new View(),mPagerScroll; int pages=2;
 Delegate mPagerTouchDelegate,nextDelegate; MotionEvent mPagerDelegateDown;
 Object getContext(){return null;} int quickPageCount(){return pages;}
 void offsetDescendantRectToMyCoords(View v,android.graphics.Rect r){}
 boolean dragHit(View v,float x,float y){return x>=0 && x<100 && y>=0 && y<v.bottom;}
 Delegate pagerTouchExtension(){return nextDelegate;}
 void clearPagerTouchDelegate(){clearPagerTouchDelegate(true);}
 void clearPagerTouchDelegate(boolean cancel){mPagerTouchDelegate=null;mPagerDelegateDown=null;}
''' + eligibility + '''
static void check(boolean ok){if(!ok)throw new AssertionError();}
'''+dispatch.replace('super.dispatchTouchEvent(', 'dispatchToChildren(')+'''
// Substitute only the superclass boundary; retain actual method control flow.
List<Integer> actions=new ArrayList<>(); List<Boolean> replays=new ArrayList<>();
boolean downEligible;
boolean dispatchToChildren(MotionEvent e){actions.add(e.action);replays.add(mPagerDragReplay);
 if(e.action==MotionEvent.ACTION_DOWN)downEligible=insidePageGestureArea(e.x,e.y);return true;}
public static void main(String[]args){
 DispatchTest p=new DispatchTest(); Delegate d=new Delegate();p.nextDelegate=d;
 // A footer DOWN outside the action rectangle is initially ineligible.
 check(!p.insidePageGestureArea(50,110));
 p.dispatchTouchEvent(new MotionEvent(0,50,110));
 p.dispatchTouchEvent(new MotionEvent(2,35,111));
 check(d.cancels==1);check(p.actions.equals(List.of(0,2)));
 check(p.replays.equals(List.of(true,false)));check(p.downEligible);check(!p.mPagerDragReplay);
 check(!p.mPagerSequenceOwned);
 // Non-drag delegated tap remains solely with the indicator.
 p=new DispatchTest();p.nextDelegate=new Delegate();
 p.dispatchTouchEvent(new MotionEvent(0,50,110));
 p.dispatchTouchEvent(new MotionEvent(2,52,111));
 p.dispatchTouchEvent(new MotionEvent(1,52,111));
 check(p.actions.isEmpty());check(!p.mPagerSequenceOwned);
 // Overflowing selectors are not intercepted; ordinary indicators may page.
 p=new DispatchTest();p.mPagerScroll=new View();p.mPagerScroll.overflow=true;
 check(!p.insidePageGestureArea(50,50));p.mPagerScroll.overflow=false;
 check(p.insidePageGestureArea(50,50));
 p.pages=1;check(!p.insidePageGestureArea(50,50));p.pages=2;
 p.mAllMenu=true;check(!p.insidePageGestureArea(50,50));p.mDraft=new Object();
 check(p.insidePageGestureArea(50,50));
}
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            sources={
                'DispatchTest.java': source,
                'android/view/ViewConfiguration.java': 'package android.view; public class ViewConfiguration { public static ViewConfiguration get(Object c){return new ViewConfiguration();} public int getScaledTouchSlop(){return 8;} }',
                'android/graphics/Rect.java': 'package android.graphics; public class Rect {public int left,top,right,bottom; public boolean contains(int x,int y){return x>=left&&x<right&&y>=top&&y<bottom;} }',
            }
            for name,text in sources.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
            subprocess.run(['java','com.sun.tools.javac.Main','-d',tmp,*[str(root/name) for name in sources]],check=True,capture_output=True)
            subprocess.run(['java','-cp',tmp,'DispatchTest'],check=True,capture_output=True)

if __name__=='__main__':unittest.main()
