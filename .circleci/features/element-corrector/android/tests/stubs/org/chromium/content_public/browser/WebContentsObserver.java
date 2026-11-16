package org.chromium.content_public.browser;
// Pinned Chromium d331de35: observe(null) detaches; there is no destroy().
public class WebContentsObserver {
 private WebContents contents;
 public WebContentsObserver(WebContents c){observe(c);}
 public final void observe(WebContents c){if(contents==c)return;if(contents!=null)contents.observers--;contents=c;if(contents!=null)contents.observers++;}
 public void didStartNavigationInPrimaryMainFrame(NavigationHandle n){}
 public void webContentsDestroyed(){}
}
