/* Copyright (c) 2026 The Sandium Authors. All rights reserved.
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at https://mozilla.org/MPL/2.0/. */

package org.chromium.chrome.browser.firstrun;

import android.app.Activity;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CompoundButton;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Switch;

import org.chromium.base.BraveFeatureList;
import org.chromium.base.ContextUtils;
import org.chromium.brave_shields.mojom.FilterListAndroidHandler;
import org.chromium.brave_shields.mojom.SubscriptionInfo;
import org.chromium.chrome.browser.BraveFeatureUtil;
import org.chromium.chrome.browser.BraveLocalState;
import org.chromium.chrome.browser.preferences.website.BraveShieldsContentSettings;
import org.chromium.chrome.browser.profiles.Profile;
import org.chromium.chrome.browser.shields.FilterListServiceFactory;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** Brand-neutral first-run setup screen for Sandium. */
final class SandiumWelcomeSetupView {
    interface Listener {
        void onStartBrowsing();
    }

    private static final int BACKGROUND = Color.rgb(22, 24, 31);
    private static final int CARD = Color.rgb(38, 41, 50);
    private static final int SEPARATOR = Color.rgb(20, 22, 28);
    private static final int PRIMARY = Color.rgb(205, 214, 255);
    private static final int PRIMARY_TEXT = Color.rgb(39, 54, 130);
    private static final int TEXT = Color.rgb(245, 246, 250);
    private static final int SECONDARY = Color.rgb(174, 180, 194);
    private static final int SUCCESS = Color.rgb(82, 211, 133);

    private static final String PREF_BLUR_LEVEL = "sandium_page_transition_blur_level";
    private static final String PREF_DARKEN = "sandium_page_transition_darken";
    private static final String PREF_ENGINE_READY = "sandium.ad_block.engine_warmup_done";

    private final Activity mActivity;
    private final Listener mListener;
    private final Handler mHandler = new Handler(Looper.getMainLooper());
    private final Runnable mPollRunnable = this::pollFilterStatus;

    private LinearLayout mRoot;
    private LinearLayout mContent;
    private LinearLayout mAdvancedOptions;
    private TextView mMoreOptionsLabel;
    private TextView mEngineState;
    private TextView mFilterCount;
    private TextView mFinalizing;
    private TextView mPercent;
    private ProgressBar mProgress;
    private Button mStartButton;
    private FilterListAndroidHandler mFilterHandler;
    private Profile mProfile;
    private boolean mExpanded;
    private boolean mDestroyed;
    private boolean mPollInFlight;

    SandiumWelcomeSetupView(Activity activity, Listener listener) {
        mActivity = activity;
        mListener = listener;
    }

    View createView() {
        mRoot = new LinearLayout(mActivity);
        mRoot.setOrientation(LinearLayout.VERTICAL);
        mRoot.setBackgroundColor(BACKGROUND);
        mRoot.setSystemUiVisibility(0);

        ScrollView scroll = new ScrollView(mActivity);
        scroll.setFillViewport(false);
        scroll.setClipToPadding(false);
        scroll.setPadding(dp(20), dp(28), dp(20), dp(18));
        mRoot.addView(scroll, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        mContent = new LinearLayout(mActivity);
        mContent.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(mContent, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView title = text("Set up your browser", 30, TEXT, false);
        title.setGravity(Gravity.CENTER);
        mContent.addView(title, matchWrap());
        TextView subtitle = text(
                "Choose your preferred browsing experience. You can change these any time in Settings.",
                16, SECONDARY, false);
        subtitle.setGravity(Gravity.CENTER);
        subtitle.setLineSpacing(dp(2), 1f);
        LinearLayout.LayoutParams subtitleParams = matchWrap();
        subtitleParams.setMargins(dp(8), dp(8), dp(8), dp(26));
        mContent.addView(subtitle, subtitleParams);

        buildMainSettingsCard();
        buildFilterProgressCard();

        LinearLayout buttonContainer = new LinearLayout(mActivity);
        buttonContainer.setGravity(Gravity.CENTER);
        buttonContainer.setPadding(dp(16), dp(8), dp(16), dp(18));
        mRoot.addView(buttonContainer, matchWrap());

        mStartButton = new Button(mActivity);
        mStartButton.setText("Start browsing");
        mStartButton.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
        mStartButton.setTextColor(PRIMARY_TEXT);
        mStartButton.setAllCaps(false);
        mStartButton.setTypeface(Typeface.DEFAULT, Typeface.MEDIUM);
        mStartButton.setMinHeight(dp(54));
        mStartButton.setMinimumHeight(dp(54));
        mStartButton.setPadding(dp(30), 0, dp(30), 0);
        mStartButton.setBackground(roundRect(PRIMARY, 28));
        mStartButton.setEnabled(false);
        mStartButton.setAlpha(0.72f);
        mStartButton.setOnClickListener(v -> {
            if (isEngineReady()) {
                mHandler.removeCallbacks(mPollRunnable);
                mListener.onStartBrowsing();
            }
        });
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(dp(230), dp(54));
        buttonContainer.addView(mStartButton, buttonParams);

        return mRoot;
    }

    void initialize(Profile profile) {
        mProfile = profile;
        applyInitialPreferences();
        mFilterHandler = FilterListServiceFactory.getInstance()
                .getFilterListAndroidHandler(profile, null);
        // Queue the native warm-up immediately. Native code starts the additional
        // engine as soon as the first enabled subscription has downloaded successfully.
        FilterListServiceFactory.requestSandiumHomepageWarmup(profile);
        pollFilterStatus();
    }

    void destroy() {
        mDestroyed = true;
        mHandler.removeCallbacks(mPollRunnable);
        mFilterHandler = null;
    }

    private void applyInitialPreferences() {
        BraveShieldsContentSettings.setShields(
                mProfile, "", BraveShieldsContentSettings.RESOURCE_IDENTIFIER_BRAVE_SHIELDS,
                true, false);
        BraveShieldsContentSettings.setShieldsValue(
                mProfile, "", BraveShieldsContentSettings.RESOURCE_IDENTIFIER_TRACKERS,
                BraveShieldsContentSettings.BLOCK_THIRDPARTY_RESOURCE, false);
        BraveFeatureUtil.enableFeature(BraveFeatureList.ENABLE_FORCE_DARK, true, true);
        ContextUtils.getAppSharedPreferences().edit()
                .putString(PREF_BLUR_LEVEL, "medium")
                .putBoolean(PREF_DARKEN, true)
                .apply();
    }

    private void buildMainSettingsCard() {
        LinearLayout card = card();
        mContent.addView(card, matchWrap());

        addSwitchRow(card, "⬡", "Block trackers & ads",
                "Prevents trackers & ads from loading and showing in webpages",
                true, checked -> setProtectionEnabled(checked));
        addDivider(card);

        addSwitchRow(card, "☾", "Night Mode",
                "Force dark mode for web content",
                true, checked -> BraveFeatureUtil.enableFeature(
                        BraveFeatureList.ENABLE_FORCE_DARK, checked, true));
        addDivider(card);

        addBlurRow(card);
        addDivider(card);

        addSwitchRow(card, "◐", "Darken transition",
                "Dim the outgoing page during the transition",
                true, checked -> ContextUtils.getAppSharedPreferences().edit()
                        .putBoolean(PREF_DARKEN, checked).apply());
        addDivider(card);

        LinearLayout more = new LinearLayout(mActivity);
        more.setGravity(Gravity.CENTER_VERTICAL);
        more.setPadding(dp(22), dp(15), dp(22), dp(15));
        TextView plus = text("⊕", 29, PRIMARY, false);
        more.addView(plus, new LinearLayout.LayoutParams(dp(48), dp(42)));
        mMoreOptionsLabel = text("More options", 17, TEXT, false);
        more.addView(mMoreOptionsLabel, new LinearLayout.LayoutParams(0, dp(42), 1f));
        TextView arrow = text("›", 32, SECONDARY, false);
        arrow.setGravity(Gravity.CENTER);
        more.addView(arrow, new LinearLayout.LayoutParams(dp(28), dp(42)));
        more.setOnClickListener(v -> {
            mExpanded = !mExpanded;
            mAdvancedOptions.setVisibility(mExpanded ? View.VISIBLE : View.GONE);
            mMoreOptionsLabel.setText(mExpanded ? "Fewer options" : "More options");
            arrow.setText(mExpanded ? "⌄" : "›");
        });
        card.addView(more, matchWrap());

        mAdvancedOptions = new LinearLayout(mActivity);
        mAdvancedOptions.setOrientation(LinearLayout.VERTICAL);
        mAdvancedOptions.setVisibility(View.GONE);
        card.addView(mAdvancedOptions, matchWrap());
        addDivider(mAdvancedOptions);
        addSwitchRow(mAdvancedOptions, "◈", "Block third-party cookies",
                "Prevent third-party sites from storing cookies",
                isThirdPartyCookiesBlocked(), checked -> {
                    BraveShieldsContentSettings.setShieldsValue(
                            mProfile, "", BraveShieldsContentSettings.RESOURCE_IDENTIFIER_COOKIES,
                            checked ? BraveShieldsContentSettings.BLOCK_THIRDPARTY_RESOURCE
                                    : BraveShieldsContentSettings.DEFAULT,
                            false);
                });
        addDivider(mAdvancedOptions);
        addSwitchRow(mAdvancedOptions, "◇", "Strict fingerprinting protection",
                "Use stronger protection against device fingerprinting",
                isAggressiveFingerprintingEnabled(), checked -> {
                    BraveShieldsContentSettings.setShieldsValue(
                            mProfile, "",
                            BraveShieldsContentSettings.RESOURCE_IDENTIFIER_FINGERPRINTING,
                            checked ? BraveShieldsContentSettings.AGGRESSIVE
                                    : BraveShieldsContentSettings.DEFAULT,
                            false);
                });
    }

    private void buildFilterProgressCard() {
        LinearLayout card = card();
        LinearLayout.LayoutParams params = matchWrap();
        params.setMargins(0, dp(20), 0, dp(14));
        mContent.addView(card, params);

        LinearLayout heading = new LinearLayout(mActivity);
        heading.setGravity(Gravity.CENTER_VERTICAL);
        heading.setPadding(dp(20), dp(18), dp(20), dp(10));
        card.addView(heading, matchWrap());

        TextView spinner = text("⟳", 34, PRIMARY, false);
        spinner.setGravity(Gravity.CENTER);
        heading.addView(spinner, new LinearLayout.LayoutParams(dp(54), dp(52)));

        LinearLayout labels = new LinearLayout(mActivity);
        labels.setOrientation(LinearLayout.VERTICAL);
        labels.setPadding(dp(8), 0, 0, 0);
        heading.addView(labels, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        TextView title = text("Updating ad blocking rules...", 16, TEXT, false);
        labels.addView(title, matchWrap());
        TextView subtitle = text(
                "Downloading and applying filter updates in the background",
                13, SECONDARY, false);
        subtitle.setPadding(0, dp(4), 0, 0);
        labels.addView(subtitle, matchWrap());

        LinearLayout progressRow = new LinearLayout(mActivity);
        progressRow.setGravity(Gravity.CENTER_VERTICAL);
        progressRow.setPadding(dp(72), dp(2), dp(20), dp(14));
        card.addView(progressRow, matchWrap());

        mProgress = new ProgressBar(mActivity, null, android.R.attr.progressBarStyleHorizontal);
        mProgress.setMax(100);
        mProgress.setProgress(0);
        mProgress.setProgressTintList(ColorStateList.valueOf(PRIMARY));
        mProgress.setProgressBackgroundTintList(ColorStateList.valueOf(Color.rgb(64, 68, 78)));
        progressRow.addView(mProgress, new LinearLayout.LayoutParams(0, dp(7), 1f));

        mPercent = text("0%", 14, TEXT, false);
        mPercent.setGravity(Gravity.RIGHT | Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams percentParams = new LinearLayout.LayoutParams(dp(54), dp(30));
        percentParams.setMargins(dp(12), 0, 0, 0);
        progressRow.addView(mPercent, percentParams);

        View divider = new View(mActivity);
        divider.setBackgroundColor(Color.rgb(69, 73, 83));
        LinearLayout.LayoutParams dividerParams = matchWrap();
        dividerParams.height = dp(1);
        dividerParams.setMargins(dp(20), 0, dp(20), dp(12));
        card.addView(divider, dividerParams);

        mEngineState = statusLine("●", "Ad blocker engine: Waiting for first rule", SECONDARY);
        mFilterCount = statusLine("●", "Filters: 0 of 0 updated", SECONDARY);
        mFinalizing = statusLine("○", "Finalizing: Waiting for filter download...", SECONDARY);
        mEngineState.setPadding(dp(22), dp(4), dp(18), dp(4));
        mFilterCount.setPadding(dp(22), dp(4), dp(18), dp(4));
        mFinalizing.setPadding(dp(22), dp(4), dp(18), dp(16));
        card.addView(mEngineState, matchWrap());
        card.addView(mFilterCount, matchWrap());
        card.addView(mFinalizing, matchWrap());
    }

    private TextView statusLine(String marker, String value, int color) {
        TextView line = text(marker + "   " + value, 14, color, false);
        return line;
    }

    private void addBlurRow(LinearLayout parent) {
        LinearLayout row = new LinearLayout(mActivity);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(22), dp(14), dp(20), dp(14));
        parent.addView(row, matchWrap());

        TextView icon = text("▱", 30, PRIMARY, false);
        row.addView(icon, new LinearLayout.LayoutParams(dp(48), dp(46)));

        LinearLayout labels = new LinearLayout(mActivity);
        labels.setOrientation(LinearLayout.VERTICAL);
        row.addView(labels, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        labels.addView(text("Page transition blur", 17, TEXT, false), matchWrap());
        TextView summary = text(
                "Set how strongly the previous page blurs when opening another website",
                13, SECONDARY, false);
        summary.setPadding(0, dp(3), dp(8), 0);
        labels.addView(summary, matchWrap());

        Spinner spinner = new Spinner(mActivity);
        List<String> values = Arrays.asList("Low", "Medium", "High");
        ArrayAdapter<String> adapter = new ArrayAdapter<>(
                mActivity, android.R.layout.simple_spinner_item, values);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinner.setAdapter(adapter);
        String current = ContextUtils.getAppSharedPreferences()
                .getString(PREF_BLUR_LEVEL, "medium");
        int selected = values.indexOf(capitalize(current));
        spinner.setSelection(selected < 0 ? 1 : selected, false);
        spinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(android.widget.AdapterView<?> parentView, View view,
                    int position, long id) {
                String value = values.get(position).toLowerCase(java.util.Locale.ROOT);
                ContextUtils.getAppSharedPreferences().edit().putString(PREF_BLUR_LEVEL, value).apply();
            }

            @Override
            public void onNothingSelected(android.widget.AdapterView<?> parentView) {}
        });
        LinearLayout.LayoutParams spinnerParams = new LinearLayout.LayoutParams(dp(116), dp(48));
        spinnerParams.setMargins(dp(8), 0, 0, 0);
        row.addView(spinner, spinnerParams);
    }

    private void addSwitchRow(LinearLayout parent, String glyph, String title, String summary,
            boolean checked, java.util.function.Consumer<Boolean> onChanged) {
        LinearLayout row = new LinearLayout(mActivity);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(22), dp(13), dp(20), dp(13));
        parent.addView(row, matchWrap());

        TextView icon = text(glyph, 29, PRIMARY, false);
        icon.setGravity(Gravity.CENTER);
        row.addView(icon, new LinearLayout.LayoutParams(dp(48), dp(48)));

        LinearLayout labels = new LinearLayout(mActivity);
        labels.setOrientation(LinearLayout.VERTICAL);
        labels.setPadding(dp(8), 0, dp(8), 0);
        row.addView(labels, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        labels.addView(text(title, 17, TEXT, false), matchWrap());
        TextView detail = text(summary, 13, SECONDARY, false);
        detail.setPadding(0, dp(3), 0, 0);
        labels.addView(detail, matchWrap());

        Switch toggle = new Switch(mActivity);
        toggle.setChecked(checked);
        toggle.setShowText(false);
        toggle.setThumbTintList(new ColorStateList(
                new int[][] { new int[] { android.R.attr.state_checked }, new int[] {} },
                new int[] { PRIMARY, Color.rgb(185, 188, 197) }));
        toggle.setTrackTintList(new ColorStateList(
                new int[][] { new int[] { android.R.attr.state_checked }, new int[] {} },
                new int[] { Color.rgb(110, 127, 192), Color.rgb(87, 91, 101) }));
        toggle.setOnCheckedChangeListener((button, value) -> onChanged.accept(value));
        row.addView(toggle, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
    }

    private void setProtectionEnabled(boolean enabled) {
        BraveShieldsContentSettings.setShields(
                mProfile, "", BraveShieldsContentSettings.RESOURCE_IDENTIFIER_BRAVE_SHIELDS,
                enabled, false);
        if (enabled) {
            BraveShieldsContentSettings.setShieldsValue(
                    mProfile, "", BraveShieldsContentSettings.RESOURCE_IDENTIFIER_TRACKERS,
                    BraveShieldsContentSettings.BLOCK_THIRDPARTY_RESOURCE, false);
        }
    }

    private boolean isThirdPartyCookiesBlocked() {
        String value = BraveShieldsContentSettings.getShieldsValue(
                mProfile, "", BraveShieldsContentSettings.RESOURCE_IDENTIFIER_COOKIES);
        return BraveShieldsContentSettings.BLOCK_THIRDPARTY_RESOURCE.equals(value)
                || BraveShieldsContentSettings.BLOCK_RESOURCE.equals(value);
    }

    private boolean isAggressiveFingerprintingEnabled() {
        return BraveShieldsContentSettings.AGGRESSIVE.equals(
                BraveShieldsContentSettings.getShieldsValue(
                        mProfile, "", BraveShieldsContentSettings.RESOURCE_IDENTIFIER_FINGERPRINTING));
    }

    private void pollFilterStatus() {
        if (mDestroyed || mPollInFlight) return;
        mPollInFlight = true;
        boolean engineReady = isEngineReady();
        if (mFilterHandler == null) {
            updateEngineStatus(engineReady, 0, 0);
            mPollInFlight = false;
            schedulePoll();
            return;
        }
        try {
            mFilterHandler.getSubscriptions(subscriptions -> {
                if (mDestroyed) return;
                int enabled = 0;
                int downloaded = 0;
                for (SubscriptionInfo item : subscriptions) {
                    if (!item.enabled) continue;
                    enabled++;
                    long successful = item.lastSuccessfulUpdateAttempt == null
                            ? 0 : item.lastSuccessfulUpdateAttempt.internalValue;
                    if (successful > 0) downloaded++;
                }
                updateEngineStatus(isEngineReady(), downloaded, enabled);
                mPollInFlight = false;
                schedulePoll();
            });
        } catch (RuntimeException exception) {
            mPollInFlight = false;
            updateEngineStatus(engineReady, 0, 0);
            schedulePoll();
        }
    }

    private void updateEngineStatus(boolean ready, int downloaded, int total) {
        int percent = total == 0 ? 0 : Math.min(100, (downloaded * 100) / total);
        mProgress.setProgress(percent);
        mPercent.setText(percent + "%");
        mEngineState.setText(ready
                ? "✓   Ad blocker engine: Ready"
                : "○   Ad blocker engine: Waiting for first downloaded rule");
        mEngineState.setTextColor(ready ? SUCCESS : SECONDARY);
        mFilterCount.setText("✓   Filters: " + downloaded + " of " + total + " updated");
        mFilterCount.setTextColor(downloaded > 0 ? SUCCESS : SECONDARY);
        mFinalizing.setText(ready
                ? (downloaded < total
                    ? "○   Remaining filters: Updating in the background"
                    : "✓   Finalizing: Filter rules applied")
                : (downloaded > 0
                    ? "○   Finalizing: Activating the native engine..."
                    : "○   Finalizing: Waiting for filter download..."));
        mFinalizing.setTextColor(ready ? SUCCESS : SECONDARY);
        mStartButton.setEnabled(ready);
        mStartButton.setAlpha(ready ? 1f : 0.72f);
    }

    private boolean isEngineReady() {
        try {
            return BraveLocalState.get().getBoolean(PREF_ENGINE_READY);
        } catch (RuntimeException exception) {
            return false;
        }
    }

    private void schedulePoll() {
        if (!mDestroyed) mHandler.postDelayed(mPollRunnable, 900);
    }

    private LinearLayout card() {
        LinearLayout card = new LinearLayout(mActivity);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackground(roundRect(CARD, 24));
        card.setClipToOutline(true);
        return card;
    }

    private void addDivider(LinearLayout parent) {
        View divider = new View(mActivity);
        divider.setBackgroundColor(SEPARATOR);
        LinearLayout.LayoutParams params = matchWrap();
        params.height = dp(1);
        parent.addView(divider, params);
    }

    private TextView text(String value, int sizeSp, int color, boolean bold) {
        TextView view = new TextView(mActivity);
        view.setText(value);
        view.setTextSize(TypedValue.COMPLEX_UNIT_SP, sizeSp);
        view.setTextColor(color);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        view.setGravity(Gravity.CENTER_VERTICAL);
        return view;
    }

    private GradientDrawable roundRect(int color, int radiusDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(radiusDp));
        return drawable;
    }

    private int dp(int value) {
        return (int) (value * mActivity.getResources().getDisplayMetrics().density + 0.5f);
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    private static String capitalize(String value) {
        if (value == null || value.isEmpty()) return "Medium";
        return value.substring(0, 1).toUpperCase(java.util.Locale.ROOT) + value.substring(1);
    }
}
