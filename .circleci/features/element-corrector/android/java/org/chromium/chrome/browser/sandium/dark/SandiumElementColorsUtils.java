// Copyright 2026 Sandium Authors. BSD-style license.
package org.chromium.chrome.browser.sandium.dark;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Application;
import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputFilter;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.TextView;
import android.widget.ScrollView;
import android.widget.Toast;

import org.jni_zero.CalledByNative;
import org.jni_zero.JNINamespace;
import org.jni_zero.NativeMethods;
import org.chromium.base.ThreadUtils;
import org.chromium.chrome.R;
import org.chromium.chrome.browser.tab.Tab;
import org.chromium.content_public.browser.NavigationHandle;
import org.chromium.content_public.browser.WebContents;
import org.chromium.content_public.browser.WebContentsObserver;

import java.util.HashMap;
import java.util.Map;

/** Browser-owned chooser; all document/element/save authorization is independently native. */
@JNINamespace("sandium")
public final class SandiumElementColorsUtils {
    private static final Map<Tab, Controller> ACTIVE = new HashMap<>();
    private static long sNextRequest;
    private SandiumElementColorsUtils() {}

    public static void start(Context context, Tab tab) {
        ThreadUtils.assertOnUiThread();
        if (!(context instanceof Activity) || tab == null || tab.getWebContents() == null) return;
        if (!Boolean.TRUE.equals(org.chromium.chrome.browser.night_mode.SandiumDarkPages
                .enabled(tab.getWebContents(), tab.getUrl()))) return;
        Activity activity=(Activity) context;
        if (activity.isFinishing() || activity.isDestroyed()) return;
        Controller previous=ACTIVE.get(tab);
        if (previous != null) previous.close(true);
        long request=++sNextRequest;
        if (request <= 0) throw new IllegalStateException("Correction request counter exhausted");
        Controller controller=new Controller(activity,tab,request);
        ACTIVE.put(tab,controller); // Before native Start, which may synchronously call back.
        controller.observe();
        if (!SandiumElementColorsUtilsJni.get().start(tab,request)) {
            controller.message(R.string.sandium_element_unavailable);
            controller.close(true);
            return;
        }
        if (!controller.closed) controller.message(R.string.sandium_element_select_hint);
    }

    private static Controller current(Tab tab,long request) {
        ThreadUtils.assertOnUiThread();
        Controller value=ACTIVE.get(tab);
        if (value==null || value.request!=request || value.closed) return null;
        if (!value.valid()) {value.close(true);return null;}
        return value;
    }
    @CalledByNative static void onSelection(Tab tab,long request) {
        Controller value=current(tab,request);
        if (value!=null) value.showChooser();
    }
    @CalledByNative static void onSaveResult(Tab tab,long request,int result) {
        Controller value=current(tab,request);
        if (value==null || !value.saving) return;
        value.message(result==0 ? R.string.sandium_element_saved
                : result==1 ? R.string.sandium_element_visit_only : R.string.sandium_element_rejected);
        value.close(true);
    }
    @CalledByNative static void onSessionEnded(Tab tab,long request) {
        ThreadUtils.assertOnUiThread();
        Controller value=ACTIVE.get(tab);
        if (value!=null && value.request==request) value.close(false);
    }

    private static final class Controller implements Application.ActivityLifecycleCallbacks {
        final Activity activity;
        final Tab tab;
        final WebContents contents;
        final long request;
        final Handler handler=new Handler(Looper.getMainLooper());
        final Runnable timeout=()-> {
            if (!this.closed) message(this.saving ? R.string.sandium_element_rejected : R.string.sandium_element_unavailable);
            close(true);
        };
        WebContentsObserver observer;
        AlertDialog dialog;
        AlertDialog resetDialog;
        EditText color;
        RadioGroup property;
        Button preview;
        Button save;
        boolean closed;
        boolean saving;
        Controller(Activity activity,Tab tab,long request) {
            this.activity=activity;this.tab=tab;this.request=request;contents=tab.getWebContents();
        }
        boolean valid() {
            return !closed && !activity.isFinishing() && !activity.isDestroyed()
                    && tab.getWebContents()==contents && contents!=null;
        }
        void observe() {
            activity.getApplication().registerActivityLifecycleCallbacks(this);
            observer=new WebContentsObserver(contents) {
                @Override public void didStartNavigationInPrimaryMainFrame(NavigationHandle navigation) {
                    close(true); // Includes same-document and aborted navigations: reselect explicitly.
                }
                @Override public void webContentsDestroyed() {close(false);}
            };
            handler.postDelayed(timeout,60_000); // Never retain a waiting picker indefinitely.
        }
        void message(int stringId) {Toast.makeText(activity,stringId,Toast.LENGTH_SHORT).show();}
        int dp(int value) {return Math.round(value*activity.getResources().getDisplayMetrics().density);}
        TextView label(int text) {
            TextView view=new TextView(activity);view.setText(text);view.setTextColor(0xffeeeeee);
            view.setTextSize(14);view.setPadding(0,dp(8),0,dp(8));return view;
        }
        Button button(int text,Runnable action) {
            Button view=new Button(activity);view.setText(text);view.setAllCaps(false);
            view.setMinHeight(dp(48));view.setOnClickListener(v->action.run());return view;
        }
        void showChooser() {
            if (!valid() || saving || dialog!=null) return;
            handler.removeCallbacks(timeout);
            LinearLayout body=new LinearLayout(activity);body.setOrientation(LinearLayout.VERTICAL);
            body.setPadding(dp(20),dp(12),dp(20),dp(16));
            GradientDrawable background=new GradientDrawable();background.setColor(0xff1a1a1a);
            background.setCornerRadius(dp(16));body.setBackground(background);
            body.addView(label(R.string.sandium_element_choose_hint));
            property=new RadioGroup(activity);property.setOrientation(RadioGroup.VERTICAL);
            RadioButton foreground=new RadioButton(activity);foreground.setId(View.generateViewId());
            foreground.setText(R.string.sandium_element_foreground);foreground.setTextColor(0xffeeeeee);
            RadioButton surface=new RadioButton(activity);surface.setId(View.generateViewId());
            surface.setText(R.string.sandium_element_background);surface.setTextColor(0xffeeeeee);
            RadioButton image=new RadioButton(activity);image.setId(View.generateViewId());
            image.setText(R.string.sandium_element_image);image.setTextColor(0xffeeeeee);
            image.setTag(2);
            property.addView(foreground);property.addView(surface);property.addView(image);property.check(surface.getId());
            // Native property0 foreground,1 background,2 image artwork. Only these typed constants cross JNI.
            foreground.setTag(0);surface.setTag(1);body.addView(property);
            color=new EditText(activity);color.setSingleLine(true);color.setTextColor(0xffeeeeee);
            color.setHint(R.string.sandium_element_hex);color.setHintTextColor(0xffaaaaaa);
            color.setFilters(new InputFilter[]{new InputFilter.LengthFilter(7)});
            color.setText("#EEEEEE");color.setContentDescription(activity.getString(R.string.sandium_element_hex));
            body.addView(color);
            LinearLayout presets=new LinearLayout(activity);presets.setOrientation(LinearLayout.HORIZONTAL);
            for (String hex : new String[]{"#EEEEEE","#1A1A1A","#000000","#408CFF"}) {
                Button swatch=new Button(activity);swatch.setText("●");swatch.setTextColor(Color.parseColor(hex));
                swatch.setContentDescription(activity.getString(R.string.sandium_element_color)+" "+hex);
                swatch.setMinWidth(0);swatch.setMinHeight(dp(48));
                swatch.setOnClickListener(v->{if(!saving)color.setText(hex);});
                presets.addView(swatch,new LinearLayout.LayoutParams(0,dp(48),1));
            }
            body.addView(presets);
            LinearLayout actions=new LinearLayout(activity);actions.setOrientation(LinearLayout.HORIZONTAL);
            preview=button(R.string.sandium_element_preview,()->submit(false));
            save=button(R.string.sandium_element_save,()->submit(true));
            actions.addView(preview,new LinearLayout.LayoutParams(0,dp(48),1));
            actions.addView(save,new LinearLayout.LayoutParams(0,dp(48),1));body.addView(actions);
            body.addView(button(R.string.sandium_element_reset_site,()->confirmReset()));
            ScrollView scroll=new ScrollView(activity);scroll.addView(body);
            dialog=new AlertDialog.Builder(activity).setTitle(R.string.sandium_element_title)
                    .setView(scroll).setNegativeButton(R.string.sandium_element_cancel,(d,w)->close(true)).create();
            dialog.setOnDismissListener(d->close(true));
            dialog.show();Window window=dialog.getWindow();
            if(window!=null)window.setGravity(Gravity.BOTTOM);
        }
        void submit(boolean commit) {
            if (!valid() || saving) {if(!valid())close(true);return;}
            String hex=color.getText().toString().trim();
            if(!hex.matches("#[0-9a-fA-F]{6}")) {color.setError(activity.getString(R.string.sandium_element_hex));return;}
            int rgb=Integer.parseInt(hex.substring(1),16);
            View selected=property.findViewById(property.getCheckedRadioButtonId());
            if(selected==null || !(selected.getTag() instanceof Integer))return;
            int mode=(Integer)selected.getTag();
            if(mode!=0&&mode!=1&&mode!=2)return;
            if(!commit) {
                if(!SandiumElementColorsUtilsJni.get().preview(tab,request,mode,rgb)) {
                    message(R.string.sandium_element_rejected);close(true);
                }
                return;
            }
            saving=true;preview.setEnabled(false);save.setEnabled(false);color.setEnabled(false);
            // Native Save has its own five-second acknowledgment timeout.
            handler.postDelayed(timeout,7_000);
            SandiumElementColorsUtilsJni.get().save(tab,request,mode,rgb);
        }
        void confirmReset() {
            if(!valid()||saving||resetDialog!=null)return;
            resetDialog=new AlertDialog.Builder(activity).setTitle(R.string.sandium_element_reset_site)
                    .setMessage(R.string.sandium_element_reset_confirmation)
                    .setPositiveButton(R.string.sandium_element_reset_site,(d,w)->{
                        if(valid())SandiumElementColorsUtilsJni.get().resetSite(tab,request);
                        close(true);
                    }).setNegativeButton(R.string.sandium_element_cancel,null).show();
            resetDialog.setOnDismissListener(d->{if(resetDialog==d)resetDialog=null;});
        }
        void close(boolean cancelNative) {
            if(closed)return;closed=true;
            if(ACTIVE.get(tab)==this)ACTIVE.remove(tab);
            handler.removeCallbacks(timeout);
            if(observer!=null){WebContentsObserver oldObserver=observer;observer=null;oldObserver.observe(null);}
            activity.getApplication().unregisterActivityLifecycleCallbacks(this);
            if(resetDialog!=null){AlertDialog value=resetDialog;resetDialog=null;value.dismiss();}
            if(dialog!=null){AlertDialog value=dialog;dialog=null;value.dismiss();}
            if(cancelNative)SandiumElementColorsUtilsJni.get().cancel(tab,request);
        }
        @Override public void onActivityStopped(Activity owner){if(owner==activity)close(true);}
        @Override public void onActivityDestroyed(Activity owner){if(owner==activity)close(true);}
        @Override public void onActivityCreated(Activity owner,Bundle state){}
        @Override public void onActivityStarted(Activity owner){}
        @Override public void onActivityResumed(Activity owner){}
        @Override public void onActivityPaused(Activity owner){}
        @Override public void onActivitySaveInstanceState(Activity owner,Bundle state){}
    }
    @NativeMethods interface Natives {
        boolean start(Tab tab,long requestId);
        boolean preview(Tab tab,long requestId,int property,int rgb);
        void save(Tab tab,long requestId,int property,int rgb);
        void cancel(Tab tab,long requestId);
        void resetSite(Tab tab,long requestId);
    }
}
