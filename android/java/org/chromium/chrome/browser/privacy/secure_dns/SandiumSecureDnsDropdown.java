// Copyright 2026 The Sandium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package org.chromium.chrome.browser.privacy.secure_dns;

import android.content.Context;
import android.graphics.drawable.GradientDrawable;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.PopupMenu;
import android.widget.TextView;
import android.widget.Toast;
import java.util.ArrayList;
import java.util.List;
import org.chromium.components.browser_ui.styles.SemanticColorUtils;

/** Compact global control. All state and writes belong to the native DNS facade. */
public final class SandiumSecureDnsDropdown extends LinearLayout {
    private final TextView mTitle;
    private final TextView mNote;
    private final TextView mChoice;
    private final View mButton;
    private final boolean mWelcomeStyle;
    private TextView mWelcomeIcon;
    private TextView mWelcomeChevron;
    private PopupMenu mPopup;
    private boolean mNativeStartupComplete;

    public SandiumSecureDnsDropdown(Context context, boolean showGlobalNote) {
        this(context, showGlobalNote, true);
    }

    public SandiumSecureDnsDropdown(
            Context context, boolean showGlobalNote, boolean nativeStartupComplete) {
        super(context);
        mNativeStartupComplete = nativeStartupComplete;
        // Welcome has the same icon/label/picker columns as Page transition blur.
        // Shields keeps its existing compact layout and global-scope note.
        mWelcomeStyle = !showGlobalNote;
        setOrientation(VERTICAL);
        if (!mWelcomeStyle) setPadding(dp(12), dp(8), dp(12), dp(8));
        LinearLayout row = new LinearLayout(context);
        row.setGravity(mWelcomeStyle ? Gravity.TOP : Gravity.CENTER_VERTICAL);
        if (mWelcomeStyle) {
            row.setPaddingRelative(dp(16), dp(7), dp(14), dp(7));
            mWelcomeIcon = new TextView(context);
            mWelcomeIcon.setText("◎");
            mWelcomeIcon.setTextSize(23);
            mWelcomeIcon.setGravity(Gravity.CENTER);
            mWelcomeIcon.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
            row.addView(mWelcomeIcon, new LayoutParams(dp(38), dp(38)));
        }
        LinearLayout labels = new LinearLayout(context);
        labels.setOrientation(VERTICAL);
        if (mWelcomeStyle) labels.setPaddingRelative(dp(6), 0, dp(8), 0);
        mTitle = label(R.string.sandium_dns_ui_title, mWelcomeStyle ? 16 * 0.88f : 16);
        labels.addView(mTitle);
        mNote = label(showGlobalNote ? R.string.sandium_dns_ui_global
                : R.string.sandium_dns_ui_off_hint, mWelcomeStyle ? 13 * 0.88f : 12);
        if (mWelcomeStyle) mNote.setPaddingRelative(0, dp(3), dp(4), 0);
        mNote.setTextColor(SemanticColorUtils.getDefaultTextColorSecondary(getContext()));
        labels.addView(mNote);
        row.addView(labels, new LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f));
        mChoice = label(R.string.sandium_dns_ui_off, 14);
        mChoice.setGravity(Gravity.CENTER);
        mChoice.setSingleLine(true);
        mChoice.setEllipsize(TextUtils.TruncateAt.END);
        if (mWelcomeStyle) {
            LinearLayout selector = new LinearLayout(context);
            selector.setGravity(Gravity.CENTER_VERTICAL);
            selector.setPaddingRelative(dp(6), 0, dp(6), 0);
            View balance = new View(context);
            balance.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
            selector.addView(balance, new LayoutParams(dp(16), dp(38)));
            mChoice.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
            selector.addView(mChoice, new LayoutParams(0, LayoutParams.MATCH_PARENT, 1f));
            mWelcomeChevron = new TextView(context);
            mWelcomeChevron.setText("▾");
            mWelcomeChevron.setTextSize(15);
            mWelcomeChevron.setGravity(Gravity.CENTER);
            mWelcomeChevron.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
            selector.addView(mWelcomeChevron, new LayoutParams(dp(16), dp(38)));
            LayoutParams choiceParams = new LayoutParams(dp(112), dp(40));
            choiceParams.setMarginStart(dp(4));
            choiceParams.topMargin = dp(1);
            row.addView(selector, choiceParams);
            mButton = selector;
        } else {
            mChoice.setPaddingRelative(dp(10), 0, dp(10), 0);
            LayoutParams choiceParams = new LayoutParams(dp(112), dp(48));
            choiceParams.setMarginStart(dp(8));
            row.addView(mChoice, choiceParams);
            mButton = mChoice;
        }
        paintPill(SemanticColorUtils.getColorSurfaceContainer(getContext()),
                SemanticColorUtils.getColorPrimary(getContext()));
        mButton.setClickable(true);
        mButton.setFocusable(true);
        mButton.setOnClickListener(view -> showChoices());
        addView(row, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));
        refresh();
    }

    /** Welcome owns an explicitly dark palette even before the app theme is selected. */
    public void setColors(int text, int secondary, int surface, int accent) {
        mTitle.setTextColor(text); mNote.setTextColor(secondary); mChoice.setTextColor(text);
        if (mWelcomeIcon != null) mWelcomeIcon.setTextColor(accent);
        if (mWelcomeChevron != null) mWelcomeChevron.setTextColor(accent);
        paintPill(surface, accent);
    }

    private void paintPill(int surface, int accent) {
        GradientDrawable pill = new GradientDrawable();
        pill.setColor(surface);
        pill.setCornerRadius(dp(mWelcomeStyle ? 28 : 22));
        pill.setStroke(dp(1), accent);
        mButton.setBackground(pill);
    }

    /** Welcome invokes this after receiving the first native Profile. */
    public void finishNativeStartup() {
        mNativeStartupComplete = true;
        refresh();
    }

    private void refresh() {
        boolean ready = mNativeStartupComplete && SandiumSecureDns.isReady();
        mButton.setEnabled(ready && !SandiumSecureDns.isManaged());
        mButton.setAlpha(mButton.isEnabled() ? 1f : 0.5f);
        if (!ready) {
            mChoice.setText(R.string.sandium_dns_ui_loading);
            mButton.setContentDescription(mChoice.getText());
            return;
        }
        SandiumSecureDns.State state = SandiumSecureDns.getState();
        String selected = state.enabled ? state.providerName : getContext().getString(R.string.sandium_dns_ui_off);
        mChoice.setText(mWelcomeStyle ? selected
                : getContext().getString(R.string.sandium_dns_ui_picker_label, selected));
        mButton.setContentDescription(getContext().getString(R.string.sandium_dns_ui_selected, selected));
    }

    private void showChoices() {
        refresh();
        if (!mButton.isEnabled()) return;
        if (mPopup != null) mPopup.dismiss();
        // Read current native state/providers at opening, including saved custom providers.
        SandiumSecureDns.State state = SandiumSecureDns.getState();
        List<SandiumSecureDns.Provider> providers = new ArrayList<>(SandiumSecureDns.getProviders());
        PopupMenu popup = new PopupMenu(getContext(), mButton);
        mPopup = popup;
        popup.getMenu().add(0, 1, 0, R.string.sandium_dns_ui_off).setCheckable(true).setChecked(!state.enabled);
        for (int i = 0; i < providers.size(); i++) {
            SandiumSecureDns.Provider provider = providers.get(i);
            popup.getMenu().add(0, i + 2, i + 1, provider.name).setCheckable(true)
                    .setChecked(state.enabled && provider.id.equals(state.providerId));
        }
        popup.getMenu().setGroupCheckable(0, true, true);
        popup.setOnMenuItemClickListener(item -> {
            int index = item.getItemId() - 2;
            boolean saved = item.getItemId() == 1 ? SandiumSecureDns.setEnabled(false)
                    : index >= 0 && index < providers.size()
                            && SandiumSecureDns.selectProvider(providers.get(index).id);
            if (!saved) Toast.makeText(getContext(), R.string.sandium_dns_ui_failed, Toast.LENGTH_SHORT).show();
            refresh();
            return true;
        });
        popup.setOnDismissListener(menu -> { if (mPopup == menu) mPopup = null; refresh(); });
        popup.show();
    }
    @Override protected void onAttachedToWindow() { super.onAttachedToWindow(); refresh(); }
    @Override public void onWindowFocusChanged(boolean hasWindowFocus) {
        super.onWindowFocusChanged(hasWindowFocus);
        if (hasWindowFocus) refresh();
    }
    @Override protected void onDetachedFromWindow() {
        if (mPopup != null) mPopup.dismiss();
        mPopup = null;
        super.onDetachedFromWindow();
    }
    private TextView label(int resource, float size) {
        TextView view = new TextView(getContext());
        view.setText(resource); view.setTextSize(size);
        view.setTextColor(SemanticColorUtils.getDefaultTextColor(getContext()));
        return view;
    }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
}
