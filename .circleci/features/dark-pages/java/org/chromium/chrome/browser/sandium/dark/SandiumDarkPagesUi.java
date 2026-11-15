// Copyright 2026 Sandium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license.
package org.chromium.chrome.browser.sandium.dark;

import android.app.AlertDialog;
import android.content.Context;
import android.widget.Toast;
import org.chromium.chrome.R;
import org.chromium.chrome.browser.night_mode.SandiumDarkPages;
import org.chromium.chrome.browser.profiles.Profile;
import org.chromium.chrome.browser.tab.Tab;
import org.chromium.chrome.browser.sandium.dark.DarkPagePolicy.Control;
import org.chromium.chrome.browser.sandium.dark.DarkPagePolicy.Choice;
import org.chromium.url.GURL;

/** Browser-owned dark-page control. Manual element correction is a separate surface. */
public final class SandiumDarkPagesUi {
    private static final int[] LABELS = {R.string.sandium_dark_pages_enabled};
    private static final Control[] CONTROLS = {Control.DARK_PAGE};
    private static String[] choices(Context context) {
        return new String[]{context.getString(R.string.sandium_dark_pages_follow),
                context.getString(R.string.sandium_dark_pages_on),
                context.getString(R.string.sandium_dark_pages_off)};
    }
    private static boolean current(Tab tab, Profile profile, String origin) {
        return SandiumDarkPages.usable(profile) && tab != null && tab.getWebContents() != null
                && Profile.fromWebContents(tab.getWebContents()) == profile
                && origin.equals(SandiumDarkPages.origin(tab.getUrl()));
    }
    public static void showSite(Context context, Tab tab) {
        if (tab == null || tab.getWebContents() == null) return;
        Profile profile = Profile.fromWebContents(tab.getWebContents());
        GURL url = tab.getUrl(); String origin = SandiumDarkPages.origin(url);
        if (!SandiumDarkPages.usable(profile) || origin == null) return;
        String[] rows = new String[CONTROLS.length];
        String[] options = choices(context);
        for (int i=0; i<rows.length; i++) {
            Choice value = SandiumDarkPages.choice(profile, url, CONTROLS[i]);
            rows[i] = context.getString(LABELS[i]) + " · " + options[value.ordinal()];
        }
        String title = context.getString(R.string.sandium_dark_pages_title) + "\n" + origin;
        if (profile.isOffTheRecord()) title += "\n" + context.getString(R.string.sandium_dark_pages_private);
        new AlertDialog.Builder(context).setTitle(title).setItems(rows, (dialog,index) -> {
            if (!current(tab,profile,origin)) return;
            new AlertDialog.Builder(context).setTitle(LABELS[index])
                    .setSingleChoiceItems(options,
                            SandiumDarkPages.choice(profile,url,CONTROLS[index]).ordinal(),
                            (selection,which) -> {
                                // Re-check current owner; a dialog must never mutate a replacement tab/site.
                                if (current(tab,profile,origin)) {
                                    try {
                                        SandiumDarkPages.set(profile,url,CONTROLS[index],Choice.values()[which]);
                                        Toast.makeText(context,R.string.sandium_dark_pages_saved,Toast.LENGTH_SHORT).show();
                                    } catch (IllegalStateException failure) {
                                        Toast.makeText(context,R.string.sandium_dark_pages_failed,Toast.LENGTH_SHORT).show();
                                    }
                                }
                                selection.dismiss();
                            }).setNegativeButton(R.string.sandium_dark_pages_later,null).show();
        }).setNeutralButton(R.string.sandium_dark_pages_reset, (dialog,which) -> {
            if (!current(tab,profile,origin)) return;
            try {
                for (Control control : CONTROLS) SandiumDarkPages.set(profile,url,control,Choice.FOLLOW_GLOBAL);
                Toast.makeText(context,R.string.sandium_dark_pages_saved,Toast.LENGTH_SHORT).show();
            } catch (IllegalStateException failure) {
                Toast.makeText(context,R.string.sandium_dark_pages_failed,Toast.LENGTH_SHORT).show();
            }
        }).setPositiveButton(R.string.sandium_dark_pages_reload,(dialog,which) -> {
            if (current(tab,profile,origin)) tab.reload();
        }).setNegativeButton(R.string.sandium_dark_pages_later,null).show();
    }
    public static void showGlobal(Context context, Profile profile) {
        if (!SandiumDarkPages.usable(profile) || profile.isOffTheRecord()) return;
        String[] labels = new String[LABELS.length]; boolean[] checked = new boolean[LABELS.length];
        for (int i=0; i<LABELS.length; i++) {
            labels[i]=context.getString(LABELS[i]); checked[i]=SandiumDarkPages.global(profile,CONTROLS[i]);
        }
        new AlertDialog.Builder(context).setTitle(R.string.sandium_dark_pages_global)
                .setMultiChoiceItems(labels,checked,(dialog,index,on)-> {
                    if (!SandiumDarkPages.usable(profile)) { dialog.dismiss(); return; }
                    try { SandiumDarkPages.setGlobal(profile,CONTROLS[index],on); }
                    catch (IllegalStateException failure) {
                        dialog.dismiss(); // Never leave a checked state that was not saved.
                        Toast.makeText(context,R.string.sandium_dark_pages_failed,Toast.LENGTH_SHORT).show();
                    }
                }).setPositiveButton(R.string.sandium_dark_pages_later,null).show();
    }
}
