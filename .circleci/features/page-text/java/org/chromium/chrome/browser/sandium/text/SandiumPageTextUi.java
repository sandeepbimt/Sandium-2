// Copyright 2026 Sandium Authors. All rights reserved.
package org.chromium.chrome.browser.sandium.text;

import android.app.AlertDialog;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.text.Layout;
import android.text.StaticLayout;
import android.text.TextPaint;
import android.util.TypedValue;
import android.view.View;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;
import org.chromium.chrome.browser.profiles.Profile;
import org.chromium.chrome.R;

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
    // Native paragraph layout confined to the settings preview, never the webpage.
    private static final class ParagraphPreview extends View {
        private static final String SAMPLE = "Sandium keeps reading comfortable. Adjust the text size "
                + "and alignment to find a style that feels right. This sample changes instantly "
                + "while your open webpages stay unchanged.";
        private final TextPaint mPaint = new TextPaint(TextPaint.ANTI_ALIAS_FLAG);
        private StaticLayout mParagraph;
        private int mParagraphWidth = -1;
        private boolean mJustify;

        ParagraphPreview(Context context) {
            super(context);
            mPaint.setColor(Color.rgb(232, 234, 237));
            setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_YES);
        }

        void setStyle(float sizeSp, boolean justify) {
            float px = TypedValue.applyDimension(
                    TypedValue.COMPLEX_UNIT_SP, sizeSp, getResources().getDisplayMetrics());
            if (mPaint.getTextSize() == px && mJustify == justify) return;
            mPaint.setTextSize(px);
            mJustify = justify;
            mParagraph = null;
            requestLayout();
            invalidate();
        }

        @Override
        protected void onMeasure(int widthSpec, int heightSpec) {
            int width = MeasureSpec.getSize(widthSpec);
            int contentWidth = Math.max(1, width - getPaddingLeft() - getPaddingRight());
            if (mParagraph == null || mParagraphWidth != contentWidth) {
                mParagraphWidth = contentWidth;
                mParagraph = StaticLayout.Builder.obtain(SAMPLE, 0, SAMPLE.length(), mPaint, contentWidth)
                        .setAlignment(Layout.Alignment.ALIGN_NORMAL)
                        .setBreakStrategy(Layout.BREAK_STRATEGY_SIMPLE)
                        .setLineSpacing(0f, 1.3f)
                        .setJustificationMode(mJustify
                                ? android.graphics.text.LineBreaker.JUSTIFICATION_MODE_INTER_WORD
                                : android.graphics.text.LineBreaker.JUSTIFICATION_MODE_NONE)
                        .build();
            }
            setMeasuredDimension(width, resolveSize(
                    mParagraph.getHeight() + getPaddingTop() + getPaddingBottom(), heightSpec));
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            if (mParagraph == null) return;
            int save = canvas.save();
            canvas.translate(getPaddingLeft(), getPaddingTop());
            mParagraph.draw(canvas);
            canvas.restoreToCount(save);
        }

        @Override
        public void onInitializeAccessibilityNodeInfo(AccessibilityNodeInfo info) {
            super.onInitializeAccessibilityNodeInfo(info);
            info.setClassName(TextView.class.getName());
            info.setText(SAMPLE);
        }
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
        CheckBox justify = new CheckBox(c); justify.setText(R.string.sandium_page_text_justify);
        justify.setChecked(initial.isJustificationEnabled()); body.addView(justify);
        // A local reading surface beneath both controls.
        ParagraphPreview sample = new ParagraphPreview(c);
        sample.setPadding(pad, pad, pad, pad);
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
            sample.setStyle(16f * percent / 100f, justified);
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
                .setNegativeButton("Cancel", null).setPositiveButton("Save", null).create();
        // The spacing overload belongs to AlertDialog, not AlertDialog.Builder.
        dialog.setView(scroll, 0, 0, 0, 0);
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
