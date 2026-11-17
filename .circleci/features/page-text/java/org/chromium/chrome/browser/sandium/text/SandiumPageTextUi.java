// Copyright 2026 Sandium Authors. All rights reserved.
package org.chromium.chrome.browser.sandium.text;

import android.app.AlertDialog;
import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.view.View;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;
import org.chromium.chrome.browser.profiles.Profile;

/** Edits a draft and a local sample only. Saving never executes script or mutates the document. */
public final class SandiumPageTextUi {
    private SandiumPageTextUi() {}
    public static void showGlobal(Context context, Profile profile) {
        if (context == null || !SandiumPageText.usable(profile)) return;
        show(context, profile);
    }
    private static TextView text(Context c, String value) {
        TextView view = new TextView(c); view.setText(value); view.setTextSize(16);
        return view;
    }
    private static void show(Context c, Profile profile) {
        PageTextPolicy.Settings initial = SandiumPageText.global(profile);
        LinearLayout body = new LinearLayout(c); body.setOrientation(LinearLayout.VERTICAL);
        int pad = Math.round(20 * c.getResources().getDisplayMetrics().density);
        // No stacked bottom padding between the preview and native dialog actions.
        body.setPadding(pad, pad / 2, pad, 0);
        TextView size = text(c, ""); body.addView(size);
        SeekBar slider = new SeekBar(c); slider.setMax((PageTextPolicy.MAX_SCALE - PageTextPolicy.MIN_SCALE) / PageTextPolicy.SCALE_STEP);
        slider.setProgress((initial.scalePercent - PageTextPolicy.MIN_SCALE) / PageTextPolicy.SCALE_STEP);
        slider.setContentDescription("Webpage text size"); body.addView(slider);
        CheckBox justify = new CheckBox(c); justify.setText("Justify article text");
        justify.setChecked(initial.isJustificationEnabled()); body.addView(justify);
        // A local reading surface beneath both controls.
        TextView sample = text(c, "Sandium keeps reading comfortable. Adjust the text size and alignment to find a style that feels right. This sample changes instantly while your open webpages stay unchanged.");
        sample.setTextColor(Color.rgb(232, 234, 237));
        sample.setPadding(pad, pad, pad, pad);
        sample.setLineSpacing(0, 1.3f);
        GradientDrawable sampleBackground = new GradientDrawable();
        sampleBackground.setColor(Color.rgb(24, 26, 29));
        sampleBackground.setCornerRadius(12 * c.getResources().getDisplayMetrics().density);
        sample.setBackground(sampleBackground);
        LinearLayout.LayoutParams sampleParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        sampleParams.setMargins(0, pad / 2, 0, 0);
        body.addView(sample, sampleParams);
        if (profile.isOffTheRecord()) {
            TextView privateNote = text(c, "Private session only. Changes are not saved to your regular profile.");
            privateNote.setTextSize(13); body.addView(privateNote);
        }
        Runnable preview = () -> {
            int percent = PageTextPolicy.MIN_SCALE + slider.getProgress() * PageTextPolicy.SCALE_STEP;
            boolean justified = justify.isChecked();
            size.setText(percent == 100 ? "Text size · Website default (100%)" : "Text size · " + percent + "%");
            sample.setTextSize(16f * percent / 100f);
            // Native sample widget only, never the webpage. Device API is >= Android 8 here.
            sample.setJustificationMode(justified
                    ? android.text.Layout.JUSTIFICATION_MODE_INTER_WORD
                    : android.text.Layout.JUSTIFICATION_MODE_NONE);
        };
        slider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar v, int value, boolean user) { preview.run(); }
            @Override public void onStartTrackingTouch(SeekBar v) {}
            @Override public void onStopTrackingTouch(SeekBar v) {}
        });
        justify.setOnCheckedChangeListener((v, checked) -> preview.run());
        preview.run();
        ScrollView scroll = new ScrollView(c); scroll.addView(body);
        AlertDialog dialog = new AlertDialog.Builder(c).setTitle("Webpage text")
                .setView(scroll, 0, 0, 0, 0).setNegativeButton("Cancel", null).setPositiveButton("Save", null).create();
        dialog.setOnShowListener(ignored -> {
            View.OnClickListener save = button -> {
                if (!SandiumPageText.usable(profile)) {
                    Toast.makeText(c, "Settings are unavailable. Please reopen them.", Toast.LENGTH_SHORT).show();
                    dialog.dismiss(); return;
                }
                try {
                    PageTextPolicy.Settings value = new PageTextPolicy.Settings(
                            PageTextPolicy.MIN_SCALE + slider.getProgress() * PageTextPolicy.SCALE_STEP, justify.isChecked());
                    SandiumPageText.setGlobal(profile, value);
                    dialog.dismiss();
                    Toast.makeText(c, "Saved. Applies on next page load.", Toast.LENGTH_SHORT).show();
                } catch (IllegalStateException failure) {
                    Toast.makeText(c, "Could not save text settings. Please try again.", Toast.LENGTH_SHORT).show();
                }
            };
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(save);
        });
        dialog.show();
    }
}
