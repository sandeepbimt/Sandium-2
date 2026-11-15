import android.content.Context;
import android.content.res.Resources;
import android.util.TypedValue;
import org.chromium.chrome.browser.sandium.video.SandiumVideoController;
public class VideoThemeTest {
 static class C extends Context { int mode; public Resources.Theme getTheme(){return new Resources.Theme(){
  public boolean resolveAttribute(int a,TypedValue v,boolean refs){
   if(mode==0)return false;if(mode==1){v.type=28;v.data=0xffaabbcc;}if(mode>=2)v.resourceId=5;if(mode==4){v.resourceId=0;v.type=3;}return true;
  }};}
  public int getColor(int id){if(mode==3)throw new Resources.NotFoundException();return 0xff112233;}
 }
 public static void main(String[] a)throws Exception {
  var method=SandiumVideoController.class.getDeclaredMethod("themeColor",Context.class,int.class,int.class);method.setAccessible(true);
  C c=new C();int[] expected={7,0xffaabbcc,0xff112233,7,7};
  for(int i=0;i<5;i++){c.mode=i;if((int)method.invoke(null,c,1,7)!=expected[i])throw new AssertionError(i);}
  System.out.println("5 shared-theme resolution checks passed (Android doubles)");
 }
}
