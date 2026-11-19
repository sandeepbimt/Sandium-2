// Copyright 2026 The Sandium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package org.chromium.chrome.browser.privacy.secure_dns;

import android.content.Context;
import android.graphics.drawable.GradientDrawable;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.PopupMenu;
import android.widget.TextView;
import android.widget.Toast;
import java.util.ArrayList;
import java.util.List;

/** Compact global control. All state and writes belong to the native DNS facade. */
public final class SandiumSecureDnsDropdown extends LinearLayout {
    private final TextView mTitle;
    private final TextView mNote;
    private final TextView mChoice;
    private final TextView mManage;
    private PopupMenu mPopup;
    private boolean mNativeStartupComplete;

    public SandiumSecureDnsDropdown(Context context, boolean showGlobalNote) {
        this(context, showGlobalNote, true);
    }

    public SandiumSecureDnsDropdown(
            Context context, boolean showGlobalNote, boolean nativeStartupComplete) {
        super(context);
        mNativeStartupComplete = nativeStartupComplete;
        setOrientation(VERTICAL);
        setPadding(dp(12), dp(8), dp(12), dp(8));
        LinearLayout row = new LinearLayout(context);
        row.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout labels = new LinearLayout(context);
        labels.setOrientation(VERTICAL);
        mTitle = label(R.string.sandium_dns_ui_title, 16);
        labels.addView(mTitle);
        mNote = label(showGlobalNote ? R.string.sandium_dns_ui_global
                : R.string.sandium_dns_ui_off_hint, 12);
        mNote.setTextColor(color(com.google.android.material.R.attr.colorOnSurfaceVariant));
        labels.addView(mNote);
        row.addView(labels, new LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f));
        mChoice = label(R.string.sandium_dns_ui_off, 14);
        mChoice.setGravity(Gravity.CENTER);
        mChoice.setSingleLine(true);
        mChoice.setEllipsize(TextUtils.TruncateAt.END);
        mChoice.setPadding(dp(10), 0, dp(10), 0);
        GradientDrawable pill = new GradientDrawable();
        pill.setColor(color(com.google.android.material.R.attr.colorSurfaceContainer));
        pill.setCornerRadius(dp(22));
        pill.setStroke(dp(1), color(com.google.android.material.R.attr.colorPrimary));
        mChoice.setBackground(pill);
        mChoice.setClickable(true);
        mChoice.setFocusable(true);
        mChoice.setOnClickListener(view -> showChoices());
        LayoutParams choiceParams = new LayoutParams(dp(136), dp(48));
        choiceParams.setMarginStart(dp(8));
        row.addView(mChoice, choiceParams);
        addView(row, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));
        mManage = label(R.string.sandium_dns_ui_manage, 12);
        mManage.setTextColor(color(com.google.android.material.R.attr.colorPrimary));
        mManage.setGravity(Gravity.CENTER_VERTICAL);
        mManage.setMinHeight(dp(48));
        mManage.setFocusable(true);
        mManage.setOnClickListener(view -> SandiumSecureDns.openSettings(context));
        // Provider creation belongs only to Settings, not either compact dropdown.
        if (showGlobalNote) addView(mManage);
        refresh();
    }

    /** Welcome owns an explicitly dark palette even before the app theme is selected. */
    public void setColors(int text, int secondary, int surface, int accent) {
        mTitle.setTextColor(text); mNote.setTextColor(secondary); mChoice.setTextColor(text);
        mManage.setTextColor(accent);
        GradientDrawable pill = new GradientDrawable();
        pill.setColor(surface); pill.setCornerRadius(dp(22)); pill.setStroke(dp(1), accent);
        mChoice.setBackground(pill);
    }

    /** Welcome invokes this after receiving the first native Profile. */
    public void finishNativeStartup() {
        mNativeStartupComplete = true;
        refresh();
    }

    private void refresh() {
        boolean ready = mNativeStartupComplete && SandiumSecureDns.isReady();
        mChoice.setEnabled(ready && !SandiumSecureDns.isManaged());
        mManage.setEnabled(ready);
        mChoice.setAlpha(mChoice.isEnabled() ? 1f : 0.5f);
        if (!ready) {
            mChoice.setText(R.string.sandium_dns_ui_loading);
            return;
        }
        SandiumSecureDns.State state = SandiumSecureDns.getState();
        String selected = state.enabled ? state.providerName : getContext().getString(R.string.sandium_dns_ui_off);
        mChoice.setText(getContext().getString(R.string.sandium_dns_ui_picker_label, selected));
        mChoice.setContentDescription(getContext().getString(R.string.sandium_dns_ui_selected, selected));
    }

    private void showChoices() {
        refresh();
        if (!mChoice.isEnabled()) return;
        if (mPopup != null) mPopup.dismiss();
        // Read current native state/providers at opening, including saved custom providers.
        SandiumSecureDns.State state = SandiumSecureDns.getState();
        List<SandiumSecureDns.Provider> providers = new ArrayList<>(SandiumSecureDns.getProviders());
        PopupMenu popup = new PopupMenu(getContext(), mChoice);
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
    private TextView label(int resource, int size) {
        TextView view = new TextView(getContext());
        view.setText(resource); view.setTextSize(size);
        view.setTextColor(color(com.google.android.material.R.attr.colorOnSurface));
        return view;
    }
    private int color(int attr) {
        TypedValue value = new TypedValue();
        if (!getContext().getTheme().resolveAttribute(attr, value, true)) return 0;
        return value.resourceId == 0 ? value.data : getContext().getColor(value.resourceId);
    }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
}
