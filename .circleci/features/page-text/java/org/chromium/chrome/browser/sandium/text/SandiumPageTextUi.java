// Copyright 2026 Sandium Authors. All rights reserved.
package org.chromium.chrome.browser.sandium.text;

import android.app.AlertDialog;
import android.content.Context;
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
        body.setPadding(pad, pad / 2, pad, pad / 2);
        TextView size = text(c, ""); body.addView(size);
        SeekBar slider = new SeekBar(c); slider.setMax((PageTextPolicy.MAX_SCALE - PageTextPolicy.MIN_SCALE) / PageTextPolicy.SCALE_STEP);
        slider.setProgress((initial.scalePercent - PageTextPolicy.MIN_SCALE) / PageTextPolicy.SCALE_STEP);
        slider.setContentDescription("Webpage text size"); body.addView(slider);
        CheckBox typography = new CheckBox(c); typography.setText("Reader typography");
        typography.setChecked(initial.enabled); body.addView(typography);
        CheckBox justify = new CheckBox(c); justify.setText("Justify article text");
        justify.setChecked(initial.justify); body.addView(justify);
        TextView sampleLabel = text(c, "Sample preview only · Website fonts may differ"); body.addView(sampleLabel);
        TextView sample = text(c, "Sandium keeps reading comfortable. Change text size here without moving the page behind this panel.");
        sample.setPadding(0, pad / 2, 0, pad / 2); body.addView(sample);
        TextView note = text(c, "Replaces the website’s text adjustment; actual size and layout depend on the site. Applies on the next load. Open pages stay unchanged until reloaded.");
        note.setTextSize(13); body.addView(note);
        if (profile.isOffTheRecord()) {
            TextView privateNote = text(c, "Private session only. Changes are not saved to your regular profile.");
            privateNote.setTextSize(13); body.addView(privateNote);
        }
        Runnable preview = () -> {
            int percent = PageTextPolicy.MIN_SCALE + slider.getProgress() * PageTextPolicy.SCALE_STEP;
            boolean typeOn = typography.isChecked();
            boolean justified = justify.isChecked();
            size.setText(percent == 100 ? "Text size · Website default (100%)" : "Text size · Native adjustment " + percent + "%");
            justify.setEnabled(typeOn);
            sample.setTextSize(16f * percent / 100f);
            // Native sample widget only, never the webpage. Device API is >= Android 8 here.
            sample.setJustificationMode(typeOn && justified
                    ? android.text.Layout.JUSTIFICATION_MODE_INTER_WORD
                    : android.text.Layout.JUSTIFICATION_MODE_NONE);
        };
        slider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar v, int value, boolean user) { preview.run(); }
            @Override public void onStartTrackingTouch(SeekBar v) {}
            @Override public void onStopTrackingTouch(SeekBar v) {}
        });
        typography.setOnCheckedChangeListener((v, checked) -> preview.run());
        justify.setOnCheckedChangeListener((v, checked) -> preview.run());
        preview.run();
        ScrollView scroll = new ScrollView(c); scroll.addView(body);
        AlertDialog dialog = new AlertDialog.Builder(c).setTitle("Webpage text")
                .setView(scroll).setNegativeButton("Cancel", null).setPositiveButton("Save", null).create();
        dialog.setOnShowListener(ignored -> {
            View.OnClickListener save = button -> {
                if (!SandiumPageText.usable(profile)) {
                    Toast.makeText(c, "Settings are unavailable. Please reopen them.", Toast.LENGTH_SHORT).show();
                    dialog.dismiss(); return;
                }
                try {
                    PageTextPolicy.Settings value = new PageTextPolicy.Settings(typography.isChecked(),
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
