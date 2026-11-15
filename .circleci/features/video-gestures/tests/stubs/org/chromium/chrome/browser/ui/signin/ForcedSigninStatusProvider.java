package org.chromium.chrome.browser.ui.signin;
public class ForcedSigninStatusProvider { public static boolean showing;public static ForcedSigninStatusProvider getForProfile(org.chromium.chrome.browser.profiles.Profile p){return new ForcedSigninStatusProvider();}public boolean isForcedSigninShowing(){return showing;} }
