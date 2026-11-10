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
    private static final int DISABLED_BUTTON = Color.rgb(66, 70, 82);
    private static final int DISABLED_BUTTON_TEXT = Color.rgb(176, 181, 194);
    private static final int TEXT = Color.rgb(245, 246, 250);
    private static final int SECONDARY = Color.rgb(174, 180, 194);
    private static final int SUCCESS = Color.rgb(82, 211, 133);

    private static final String PREF_BLUR_LEVEL = "sandium_page_transition_blur_level";
    private static final String PREF_DARKEN = "sandium_page_transition_darken";
    private static final String PREF_ENGINE_READY = "sandium.ad_block.engine_warmup_done";

    private final Activity mActivity;
    private final Listener mListener;
    private final Handler mHandler = new Handler(Looper.getMainLooper());
    private final List<Switch> mSwitches = new ArrayList<>();
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
    private boolean mCanStartBrowsing;

    SandiumWelcomeSetupView(Activity activity, Listener listener) {
        mActivity = activity;
        mListener = listener;
    }

    View createView() {
        mActivity.getWindow().setStatusBarColor(BACKGROUND);
        mActivity.getWindow().setNavigationBarColor(BACKGROUND);
        mActivity.getWindow().getDecorView().setSystemUiVisibility(0);
        mRoot = new LinearLayout(mActivity);
        mRoot.setOrientation(LinearLayout.VERTICAL);
        mRoot.setBackgroundColor(BACKGROUND);
        mRoot.setSystemUiVisibility(0);

        // The welcome screen is intentionally a single, non-scrollable page.
        // Its compact vertical rhythm keeps progress, every primary setting, and
        // the Start action visible together on common Android phone heights.
        mContent = new LinearLayout(mActivity);
        mContent.setOrientation(LinearLayout.VERTICAL);
        mContent.setPadding(dp(14), dp(5), dp(14), 0);
        mRoot.addView(mContent, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        TextView title = text("Set up your browser", 24, TEXT, false);
        title.setGravity(Gravity.CENTER);
        mContent.addView(title, matchWrap());
        TextView subtitle = text(
                "Choose your preferred browsing experience. Change these anytime in Settings.",
                11, SECONDARY, false);
        subtitle.setGravity(Gravity.CENTER);
        subtitle.setMaxLines(2);
        subtitle.setLineSpacing(0, 1f);
        LinearLayout.LayoutParams subtitleParams = matchWrap();
        subtitleParams.setMargins(dp(4), dp(2), dp(4), dp(8));
        mContent.addView(subtitle, subtitleParams);

        buildFilterProgressCard();
        buildMainSettingsCard();

        LinearLayout buttonContainer = new LinearLayout(mActivity);
        buttonContainer.setGravity(Gravity.CENTER);
        buttonContainer.setPadding(dp(16), dp(3), dp(16), dp(5));
        mRoot.addView(buttonContainer, matchWrap());

        mStartButton = new Button(mActivity);
        mStartButton.setText("Start browsing");
        mStartButton.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        mStartButton.setTextColor(DISABLED_BUTTON_TEXT);
        mStartButton.setAllCaps(false);
        mStartButton.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        mStartButton.setMinHeight(dp(44));
        mStartButton.setMinimumHeight(dp(44));
        mStartButton.setPadding(dp(24), 0, dp(24), 0);
        mStartButton.setBackground(roundRect(DISABLED_BUTTON, 28));
        mStartButton.setEnabled(false);
        mStartButton.setAlpha(1f);
        mStartButton.setOnClickListener(v -> {
            if (mCanStartBrowsing) {
                mHandler.removeCallbacks(mPollRunnable);
                mListener.onStartBrowsing();
            }
        });
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(dp(210), dp(44));
        buttonContainer.addView(mStartButton, buttonParams);

        return mRoot;
    }

    void initialize(Profile profile) {
        mProfile = profile;
        applyInitialPreferences();
        for (Switch toggle : mSwitches) toggle.setEnabled(true);
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
        // The onboarding label promises to block both trackers and ads. Use the
        // supported full BLOCK mode. BLOCK_THIRDPARTY_RESOURCE is converted by
        // BraveShieldsContentSettings into DEFAULT for the ads JNI setter, but
        // native SetAdControlType() explicitly DCHECKs against DEFAULT.
        BraveShieldsContentSettings.setShieldsValue(
                mProfile, "", BraveShieldsContentSettings.RESOURCE_IDENTIFIER_TRACKERS,
                BraveShieldsContentSettings.BLOCK_RESOURCE, false);
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
        more.setPadding(dp(12), dp(3), dp(10), dp(3));
        TextView plus = text("⊕", 21, PRIMARY, false);
        more.addView(plus, new LinearLayout.LayoutParams(dp(34), dp(30)));
        mMoreOptionsLabel = itemText("More options", 17, TEXT, false);
        more.addView(mMoreOptionsLabel, new LinearLayout.LayoutParams(0, dp(30), 1f));
        TextView arrow = text("›", 22, SECONDARY, false);
        arrow.setGravity(Gravity.CENTER);
        more.addView(arrow, new LinearLayout.LayoutParams(dp(24), dp(30)));
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
                false, checked -> {
                    BraveShieldsContentSettings.setShieldsValue(
                            mProfile, "", BraveShieldsContentSettings.RESOURCE_IDENTIFIER_COOKIES,
                            checked ? BraveShieldsContentSettings.BLOCK_THIRDPARTY_RESOURCE
                                    : BraveShieldsContentSettings.DEFAULT,
                            false);
                });
        addDivider(mAdvancedOptions);
        addSwitchRow(mAdvancedOptions, "◇", "Strict fingerprinting protection",
                "Use stronger protection against device fingerprinting",
                false, checked -> {
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
        params.setMargins(0, dp(2), 0, dp(7));
        mContent.addView(card, params);

        LinearLayout heading = new LinearLayout(mActivity);
        heading.setGravity(Gravity.CENTER_VERTICAL);
        heading.setPadding(dp(10), dp(6), dp(10), dp(4));
        card.addView(heading, matchWrap());

        TextView spinner = text("⟳", 22, PRIMARY, false);
        spinner.setGravity(Gravity.CENTER);
        heading.addView(spinner, new LinearLayout.LayoutParams(dp(34), dp(32)));

        LinearLayout labels = new LinearLayout(mActivity);
        labels.setOrientation(LinearLayout.VERTICAL);
        labels.setPadding(dp(5), 0, 0, 0);
        heading.addView(labels, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        TextView title = text("Preparing ad-blocking protection...", 12, TEXT, false);
        labels.addView(title, matchWrap());
        TextView subtitle = text(
                "Engine starts after the first successful filter download",
                9.5f, SECONDARY, false);
        subtitle.setPadding(0, dp(4), 0, 0);
        labels.addView(subtitle, matchWrap());

        LinearLayout progressRow = new LinearLayout(mActivity);
        progressRow.setGravity(Gravity.CENTER_VERTICAL);
        progressRow.setPadding(dp(46), 0, dp(12), dp(6));
        card.addView(progressRow, matchWrap());

        mProgress = new ProgressBar(mActivity, null, android.R.attr.progressBarStyleHorizontal);
        mProgress.setMax(100);
        mProgress.setProgress(0);
        mProgress.setProgressTintList(ColorStateList.valueOf(PRIMARY));
        mProgress.setProgressBackgroundTintList(ColorStateList.valueOf(Color.rgb(64, 68, 78)));
        progressRow.addView(mProgress, new LinearLayout.LayoutParams(0, dp(5), 1f));

        mPercent = text("0%", 10, TEXT, false);
        mPercent.setGravity(Gravity.RIGHT | Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams percentParams = new LinearLayout.LayoutParams(dp(38), dp(22));
        percentParams.setMargins(dp(8), 0, 0, 0);
        progressRow.addView(mPercent, percentParams);

        View divider = new View(mActivity);
        divider.setBackgroundColor(Color.rgb(69, 73, 83));
        LinearLayout.LayoutParams dividerParams = matchWrap();
        dividerParams.height = dp(1);
        dividerParams.setMargins(dp(12), 0, dp(12), dp(4));
        card.addView(divider, dividerParams);

        mEngineState = statusLine("●", "Ad blocker engine: Waiting for first rule", SECONDARY);
        mFilterCount = statusLine("●", "Filters: 0 of 0 updated", SECONDARY);
        mFinalizing = statusLine("○", "Finalizing: Waiting for filter download...", SECONDARY);
        mEngineState.setPadding(dp(12), dp(1), dp(10), dp(1));
        mFilterCount.setPadding(dp(12), dp(1), dp(10), dp(1));
        mFinalizing.setPadding(dp(12), dp(1), dp(10), dp(7));
        card.addView(mEngineState, matchWrap());
        card.addView(mFilterCount, matchWrap());
        card.addView(mFinalizing, matchWrap());
    }

    private TextView statusLine(String marker, String value, int color) {
        TextView line = text(marker + "   " + value, 9.5f, color, false);
        return line;
    }

    private void addBlurRow(LinearLayout parent) {
        LinearLayout row = new LinearLayout(mActivity);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(12), dp(4), dp(10), dp(4));
        parent.addView(row, matchWrap());

        TextView icon = text("▱", 22, PRIMARY, false);
        row.addView(icon, new LinearLayout.LayoutParams(dp(34), dp(30)));

        LinearLayout labels = new LinearLayout(mActivity);
        labels.setOrientation(LinearLayout.VERTICAL);
        row.addView(labels, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        labels.addView(itemText("Page transition blur", 17, TEXT, false), matchWrap());
        TextView summary = itemText(
                "Set how strongly the previous page blurs when opening another website",
                13, SECONDARY, false);
        summary.setPadding(0, dp(3), dp(8), 0);
        labels.addView(summary, matchWrap());

        Spinner spinner = new Spinner(mActivity);
        List<String> values = Arrays.asList("Low", "Medium", "High");
        ArrayAdapter<String> adapter = new ArrayAdapter<String>(
                mActivity, android.R.layout.simple_spinner_item, values) {
            private TextView styledTextView(View convertView, String value) {
                TextView view = convertView instanceof TextView
                        ? (TextView) convertView : new TextView(mActivity);
                view.setText(value);
                view.setTextSize(TypedValue.COMPLEX_UNIT_SP, 8.5f);
                view.setTextColor(TEXT);
                view.setGravity(Gravity.CENTER_VERTICAL);
                view.setPadding(dp(4), 0, dp(4), 0);
                return view;
            }

            @Override
            public View getView(int position, View convertView, ViewGroup parent) {
                return styledTextView(convertView, getItem(position));
            }

            @Override
            public View getDropDownView(
                    int position, View convertView, ViewGroup parent) {
                return styledTextView(convertView, getItem(position));
            }
        };
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
        spinnerParams.width = dp(76);
        spinnerParams.height = dp(34);
        spinnerParams.setMargins(dp(4), 0, 0, 0);
        row.addView(spinner, spinnerParams);
    }

    private void addSwitchRow(LinearLayout parent, String glyph, String title, String summary,
            boolean checked, java.util.function.Consumer<Boolean> onChanged) {
        LinearLayout row = new LinearLayout(mActivity);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(12), dp(4), dp(10), dp(4));
        parent.addView(row, matchWrap());

        TextView icon = text(glyph, 20, PRIMARY, false);
        icon.setGravity(Gravity.CENTER);
        row.addView(icon, new LinearLayout.LayoutParams(dp(34), dp(32)));

        LinearLayout labels = new LinearLayout(mActivity);
        labels.setOrientation(LinearLayout.VERTICAL);
        labels.setPadding(dp(4), 0, dp(4), 0);
        row.addView(labels, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        labels.addView(itemText(title, 17, TEXT, false), matchWrap());
        TextView detail = itemText(summary, 13, SECONDARY, false);
        detail.setPadding(0, dp(1), 0, 0);
        labels.addView(detail, matchWrap());

        Switch toggle = new Switch(mActivity);
        toggle.setEnabled(false);
        mSwitches.add(toggle);
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
                    BraveShieldsContentSettings.BLOCK_RESOURCE, false);
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
        // Enable only after at least one enabled filter has a successful download
        // timestamp AND native reports that the additional ad-block engine loaded.
        mCanStartBrowsing = ready && downloaded > 0;
        mStartButton.setEnabled(mCanStartBrowsing);
        mStartButton.setTextColor(mCanStartBrowsing ? PRIMARY_TEXT : DISABLED_BUTTON_TEXT);
        mStartButton.setBackground(roundRect(
                mCanStartBrowsing ? PRIMARY : DISABLED_BUTTON, 28));
        mStartButton.setAlpha(1f);
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

    // Settings-item labels and descriptions use exactly half their previous
    // text size; the page heading, progress card, and primary action stay legible.
    private TextView itemText(String value, float originalSizeSp, int color, boolean bold) {
        return text(value, originalSizeSp * 0.5f, color, bold);
    }

    private TextView text(String value, float sizeSp, int color, boolean bold) {
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
