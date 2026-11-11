/* Copyright (c) 2026 The Sandium Authors. All rights reserved.
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at https://mozilla.org/MPL/2.0/. */

package org.chromium.chrome.browser.firstrun;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ValueAnimator;
import android.app.Activity;
import android.app.Dialog;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.ClipDrawable;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.LayerDrawable;
import android.os.Handler;
import android.os.Looper;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.Window;
import android.view.WindowManager;
import android.view.View;
import android.view.ViewGroup;
import android.view.animation.AccelerateDecelerateInterpolator;
import android.view.animation.LinearInterpolator;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.RadioButton;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Switch;

import org.chromium.base.BraveFeatureList;
import org.chromium.base.ContextUtils;
import org.chromium.brave_shields.mojom.FilterListAndroidHandler;
import org.chromium.brave_shields.mojom.SubscriptionInfo;
import org.chromium.chrome.browser.BraveFeatureUtil;
import org.chromium.chrome.browser.BraveLocalState;
import org.chromium.chrome.browser.BraveRelaunchUtils;
import org.chromium.chrome.browser.preferences.website.BraveShieldsContentSettings;
import org.chromium.chrome.browser.profiles.Profile;
import org.chromium.chrome.browser.search_engines.TemplateUrlServiceFactory;
import org.chromium.components.search_engines.TemplateUrl;
import org.chromium.components.search_engines.TemplateUrlService;
import org.chromium.chrome.browser.shields.FilterListServiceFactory;

import java.util.ArrayList;
import java.util.List;

/** Brand-neutral first-run setup screen for Sandium. */
final class SandiumWelcomeSetupView {
    interface Listener {
        void onStartBrowsing();
        void onPrepareForRestart();
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
    private static final String PREF_ENGINE_READY = "sandium.ad_block.engine_warmup_done_v2";
    private static final int REQUIRED_FILTER_COUNT = 29;

    private final Activity mActivity;
    private final Listener mListener;
    private final Handler mHandler = new Handler(Looper.getMainLooper());
    private final List<Switch> mSwitches = new ArrayList<>();
    private final Runnable mPollRunnable = this::pollFilterStatus;

    private LinearLayout mRoot;
    private LinearLayout mContent;
    private ScrollView mScrollView;
    private LinearLayout mAdvancedOptions;
    private TextView mMoreOptionsLabel;
    private TextView mEngineState;
    private TextView mFilterCount;
    private TextView mFinalizing;
    private TextView mPercent;
    private TextView mProtectionTitle;
    private TextView mProtectionSubtitle;
    private TextView mProtectionSpinner;
    private TextView mBlurValue;
    private TextView mBlurRestartHint;
    private ProgressBar mProgress;
    private Button mStartButton;
    private FilterListAndroidHandler mFilterHandler;
    private TemplateUrlService mTemplateUrlService;
    private Profile mProfile;
    private boolean mExpanded;
    private boolean mDestroyed;
    private boolean mPollInFlight;
    private boolean mCanStartBrowsing;
    private boolean mRequiresRestart;
    private boolean mRestartInProgress;
    private boolean mStartInvoked;
    private Switch mDarkenSwitch;

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

        // Keep the existing content anchored at the top. The content only extends
        // downward when More options is opened; the ScrollView handles overflow
        // without vertically recentering or shifting the current screen.
        mScrollView = new ScrollView(mActivity);
        mScrollView.setFillViewport(true);
        mScrollView.setClipToPadding(false);
        mRoot.addView(mScrollView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        mContent = new LinearLayout(mActivity);
        mContent.setOrientation(LinearLayout.VERTICAL);
        mContent.setPadding(dp(18), dp(18), dp(18), dp(12));
        mContent.setGravity(Gravity.TOP);
        mScrollView.addView(mContent, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView title = text("Set up your browser", 27, TEXT, false);
        title.setGravity(Gravity.CENTER);
        mContent.addView(title, matchWrap());
        TextView subtitle = text(
                "Choose your preferred browsing experience. Change these anytime in Settings.",
                13, SECONDARY, false);
        subtitle.setGravity(Gravity.CENTER);
        subtitle.setMaxLines(2);
        subtitle.setLineSpacing(0, 1f);
        LinearLayout.LayoutParams subtitleParams = matchWrap();
        subtitleParams.setMargins(dp(6), dp(5), dp(6), dp(14));
        mContent.addView(subtitle, subtitleParams);

        buildFilterProgressCard();
        buildMainSettingsCard();

        LinearLayout buttonContainer = new LinearLayout(mActivity);
        buttonContainer.setGravity(Gravity.CENTER);
        buttonContainer.setPadding(dp(18), dp(8), dp(18), dp(12));
        mRoot.addView(buttonContainer, matchWrap());

        mStartButton = new Button(mActivity);
        mStartButton.setText("Start browsing");
        mStartButton.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        mStartButton.setTextColor(DISABLED_BUTTON_TEXT);
        mStartButton.setAllCaps(false);
        mStartButton.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        mStartButton.setMinHeight(dp(52));
        mStartButton.setMinimumHeight(dp(52));
        mStartButton.setPadding(dp(28), 0, dp(28), 0);
        mStartButton.setBackground(roundRect(DISABLED_BUTTON, 28));
        mStartButton.setEnabled(false);
        mStartButton.setAlpha(1f);
        mStartButton.setOnClickListener(v -> startBrowsingWithFeedback());
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(dp(230), dp(52));
        buttonContainer.addView(mStartButton, buttonParams);

        return mRoot;
    }

    void initialize(Profile profile) {
        mProfile = profile;
        applyInitialPreferences();
        initializeSearchEngine();
        for (Switch toggle : mSwitches) toggle.setEnabled(true);
        if (mDarkenSwitch != null) mDarkenSwitch.setEnabled(isBlurTransitionEnabled());
        mFilterHandler = FilterListServiceFactory.getInstance()
                .getFilterListAndroidHandler(profile, null);
        // Queue the native warm-up immediately. Native code waits for all 29
        // enabled subscriptions, then marks ready only after the additional engine loads.
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
        android.content.SharedPreferences preferences = ContextUtils.getAppSharedPreferences();
        android.content.SharedPreferences.Editor editor = preferences.edit();
        if (!preferences.contains(PREF_BLUR_LEVEL)) editor.putString(PREF_BLUR_LEVEL, "medium");
        if (!preferences.contains(PREF_DARKEN)) editor.putBoolean(PREF_DARKEN, true);
        editor.commit();
        // Brave feature overrides are read during native startup; relaunch after
        // completing first run so the selected Night Mode is actually active.
        BraveFeatureUtil.enableFeature(BraveFeatureList.ENABLE_FORCE_DARK, true, true);
        mRequiresRestart = true;
    }

    private void buildMainSettingsCard() {
        LinearLayout card = card();
        mContent.addView(card, matchWrap());

        addSwitchRow(card, "⬡", "Block trackers & ads",
                "Prevents trackers & ads from loading and showing in webpages",
                true, checked -> setProtectionEnabled(checked));
        addDivider(card);

        addRestartSwitchRow(card, "☾", "Night Mode",
                "Force dark mode for web content",
                true, checked -> {
                    BraveFeatureUtil.enableFeature(BraveFeatureList.ENABLE_FORCE_DARK, checked, true);
                    mRequiresRestart = true;
                });
        addDivider(card);

        addBlurRow(card);
        addDivider(card);

        boolean blurEnabled = isBlurTransitionEnabled();
        boolean darkenChecked = blurEnabled && ContextUtils.getAppSharedPreferences()
                .getBoolean(PREF_DARKEN, true);
        mDarkenSwitch = addRestartSwitchRow(card, "◐", "Darken transition",
                "Dim the outgoing page during the transition",
                darkenChecked, checked -> {
                    if (!isBlurTransitionEnabled()) return;
                    ContextUtils.getAppSharedPreferences().edit()
                            .putBoolean(PREF_DARKEN, checked).commit();
                    mRequiresRestart = true;
                });
        mDarkenSwitch.setEnabled(blurEnabled);
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
        params.setMargins(0, dp(4), 0, dp(14));
        mContent.addView(card, params);

        LinearLayout heading = new LinearLayout(mActivity);
        heading.setGravity(Gravity.CENTER_VERTICAL);
        heading.setPadding(dp(16), dp(12), dp(16), dp(8));
        card.addView(heading, matchWrap());

        TextView spinner = text("⟳", 22, PRIMARY, false);
        spinner.setGravity(Gravity.CENTER);
        heading.addView(spinner, new LinearLayout.LayoutParams(dp(34), dp(32)));

        LinearLayout labels = new LinearLayout(mActivity);
        labels.setOrientation(LinearLayout.VERTICAL);
        labels.setPadding(dp(5), 0, 0, 0);
        heading.addView(labels, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        mProtectionSpinner = text("⟳", 22, PRIMARY, false);
        // Replace the initial decorative glyph with the status-aware indicator.
        heading.removeView(spinner);
        mProtectionSpinner.setGravity(Gravity.CENTER);
        heading.addView(mProtectionSpinner, 0, new LinearLayout.LayoutParams(dp(34), dp(32)));

        mProtectionTitle = text("Preparing ad-blocking protection...", 14, TEXT, false);
        labels.addView(mProtectionTitle, matchWrap());
        mProtectionSubtitle = text(
                "Engine starts after the first successful filter download",
                11.5f, SECONDARY, false);
        mProtectionSubtitle.setPadding(0, dp(4), 0, 0);
        labels.addView(mProtectionSubtitle, matchWrap());

        LinearLayout progressRow = new LinearLayout(mActivity);
        progressRow.setGravity(Gravity.CENTER_VERTICAL);
        progressRow.setPadding(dp(56), dp(2), dp(16), dp(10));
        card.addView(progressRow, matchWrap());

        mProgress = new ProgressBar(mActivity, null, android.R.attr.progressBarStyleHorizontal);
        mProgress.setMax(100);
        mProgress.setProgress(0);
        mProgress.setProgressTintList(ColorStateList.valueOf(PRIMARY));
        mProgress.setProgressBackgroundTintList(ColorStateList.valueOf(Color.rgb(64, 68, 78)));
        progressRow.addView(mProgress, new LinearLayout.LayoutParams(0, dp(5), 1f));

        mPercent = text("0%", 11, TEXT, false);
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
        mEngineState.setPadding(dp(16), dp(4), dp(14), dp(3));
        mFilterCount.setPadding(dp(16), dp(4), dp(14), dp(3));
        mFinalizing.setPadding(dp(16), dp(4), dp(14), dp(10));
        card.addView(mEngineState, matchWrap());
        card.addView(mFilterCount, matchWrap());
        card.addView(mFinalizing, matchWrap());
    }

    private TextView statusLine(String marker, String value, int color) {
        TextView line = text(marker + "   " + value, 11.5f, color, false);
        return line;
    }

    private void addBlurRow(LinearLayout parent) {
        LinearLayout row = new LinearLayout(mActivity);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(16), dp(9), dp(14), dp(9));
        parent.addView(row, matchWrap());

        TextView icon = text("▱", 23, PRIMARY, false);
        icon.setGravity(Gravity.CENTER);
        row.addView(icon, new LinearLayout.LayoutParams(dp(38), dp(38)));

        LinearLayout labels = new LinearLayout(mActivity);
        labels.setOrientation(LinearLayout.VERTICAL);
        labels.setPadding(dp(6), 0, dp(8), 0);
        row.addView(labels, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        labels.addView(itemText("Page transition blur", 17, TEXT, false), matchWrap());
        TextView summary = itemText(
                "Choose how strongly the previous page blurs during navigation",
                13, SECONDARY, false);
        summary.setPadding(0, dp(3), dp(4), 0);
        labels.addView(summary, matchWrap());

        LinearLayout selector = new LinearLayout(mActivity);
        selector.setGravity(Gravity.CENTER_VERTICAL);
        selector.setPadding(dp(10), 0, dp(8), 0);
        selector.setBackground(roundRect(CARD, 12));
        mBlurValue = text(getBlurLevelLabel(), 12, TEXT, false);
        mBlurValue.setSingleLine(true);
        selector.addView(mBlurValue, new LinearLayout.LayoutParams(0, dp(40), 1f));
        TextView chevron = text("⌄", 17, SECONDARY, false);
        chevron.setGravity(Gravity.CENTER);
        selector.addView(chevron, new LinearLayout.LayoutParams(dp(20), dp(40)));
        selector.setOnClickListener(v -> showBlurLevelPicker());
        LinearLayout.LayoutParams selectorParams =
                new LinearLayout.LayoutParams(dp(116), dp(42));
        selectorParams.setMargins(dp(6), 0, 0, 0);
        row.addView(selector, selectorParams);

        mBlurRestartHint = text("↻  Needs a quick restart to apply", 11, PRIMARY, false);
        mBlurRestartHint.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        mBlurRestartHint.setLetterSpacing(0.01f);
        mBlurRestartHint.setPadding(dp(56), 0, dp(14), dp(8));
        mBlurRestartHint.setVisibility(View.GONE);
        parent.addView(mBlurRestartHint, matchWrap());
    }

    private Switch addSwitchRow(LinearLayout parent, String glyph, String title, String summary,
            boolean checked, java.util.function.Consumer<Boolean> onChanged) {
        return addSwitchRow(parent, glyph, title, summary, checked, false, onChanged);
    }

    private Switch addRestartSwitchRow(LinearLayout parent, String glyph, String title,
            String summary, boolean checked,
            java.util.function.Consumer<Boolean> onChanged) {
        return addSwitchRow(parent, glyph, title, summary, checked, true, onChanged);
    }

    private Switch addSwitchRow(LinearLayout parent, String glyph, String title, String summary,
            boolean checked, boolean showRestartHint,
            java.util.function.Consumer<Boolean> onChanged) {
        LinearLayout row = new LinearLayout(mActivity);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(16), dp(9), dp(14), dp(9));
        parent.addView(row, matchWrap());

        TextView icon = text(glyph, 23, PRIMARY, false);
        icon.setGravity(Gravity.CENTER);
        row.addView(icon, new LinearLayout.LayoutParams(dp(34), dp(32)));

        LinearLayout labels = new LinearLayout(mActivity);
        labels.setOrientation(LinearLayout.VERTICAL);
        labels.setPadding(dp(6), 0, dp(6), 0);
        row.addView(labels, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        labels.addView(itemText(title, 17, TEXT, false), matchWrap());
        TextView detail = itemText(summary, 13, SECONDARY, false);
        detail.setPadding(0, dp(1), 0, 0);
        labels.addView(detail, matchWrap());
        TextView restartHint = text("↻  Needs a quick restart to apply", 11, PRIMARY, false);
        restartHint.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        restartHint.setLetterSpacing(0.01f);
        restartHint.setPadding(dp(56), 0, dp(14), dp(8));
        restartHint.setVisibility(showRestartHint && checked ? View.VISIBLE : View.GONE);
        if (showRestartHint) parent.addView(restartHint, matchWrap());

        Switch toggle = new Switch(mActivity);
        toggle.setEnabled(false);
        mSwitches.add(toggle);
        toggle.setChecked(checked);
        toggle.setShowText(false);
        toggle.setThumbTintList(new ColorStateList(
                new int[][] {
                    new int[] { android.R.attr.state_enabled, android.R.attr.state_checked },
                    new int[] { android.R.attr.state_enabled },
                    new int[] { android.R.attr.state_checked },
                    new int[] {}
                },
                new int[] {
                    PRIMARY,
                    Color.rgb(185, 188, 197),
                    Color.rgb(172, 179, 207),
                    Color.rgb(154, 159, 172)
                }));
        toggle.setTrackTintList(new ColorStateList(
                new int[][] {
                    new int[] { android.R.attr.state_enabled, android.R.attr.state_checked },
                    new int[] { android.R.attr.state_enabled },
                    new int[] { android.R.attr.state_checked },
                    new int[] {}
                },
                new int[] {
                    Color.rgb(110, 127, 192),
                    Color.rgb(87, 91, 101),
                    Color.rgb(88, 100, 147),
                    Color.rgb(65, 69, 80)
                }));
        toggle.setOnCheckedChangeListener((button, value) -> {
            if (showRestartHint) restartHint.setVisibility(View.VISIBLE);
            onChanged.accept(value);
        });
        row.addView(toggle, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return toggle;
    }

    private void initializeSearchEngine() {
        // Set the regular and private search providers directly during first run.
        // No search-engine choice is exposed in the welcome UI.
        Profile regularProfile = mProfile.getOriginalProfile();
        mTemplateUrlService = TemplateUrlServiceFactory.getForProfile(regularProfile);
        mTemplateUrlService.runWhenLoaded(() -> {
            if (mDestroyed || mTemplateUrlService == null) return;
            if (mTemplateUrlService.isDefaultSearchManaged()) return;

            TemplateUrl google = findGoogleSearchEngine(mTemplateUrlService);
            if (google == null) return;
            mTemplateUrlService.setSearchEngine(google.getKeyword());

            // Brave maintains a separate default provider for private windows.
            // Set the primary OTR profile explicitly so the private-window provider
            // stores Google's GUID as its private default as well.
            Profile privateProfile = regularProfile.getOrCreatePrimaryOtrProfile();
            TemplateUrlService privateService =
                    TemplateUrlServiceFactory.getForProfile(privateProfile);
            privateService.runWhenLoaded(() -> {
                if (mDestroyed || privateService.isDefaultSearchManaged()) return;
                TemplateUrl privateGoogle = findGoogleSearchEngine(privateService);
                if (privateGoogle != null) {
                    privateService.setSearchEngine(privateGoogle.getKeyword());
                }
            });
        });
    }

    private TemplateUrl findGoogleSearchEngine(TemplateUrlService service) {
        for (TemplateUrl engine : service.getTemplateUrls()) {
            String name = engine.getShortName().trim().toLowerCase(java.util.Locale.ROOT);
            String keyword = engine.getKeyword().trim().toLowerCase(java.util.Locale.ROOT);
            if (name.equals("google") || name.startsWith("google ")
                    || keyword.equals("google") || keyword.startsWith("google.")) {
                return engine;
            }
        }
        return null;
    }

    private String getBlurLevelLabel() {
        String value = ContextUtils.getAppSharedPreferences()
                .getString(PREF_BLUR_LEVEL, "medium");
        return "default".equals(value) ? "Off" : capitalize(value);
    }

    private void showBlurLevelPicker() {
        final String[] values = { "Off", "Low", "Medium", "High" };
        Dialog dialog = new Dialog(mActivity);
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);

        LinearLayout container = new LinearLayout(mActivity);
        container.setOrientation(LinearLayout.VERTICAL);
        container.setPadding(dp(18), dp(14), dp(18), dp(14));
        container.setBackground(roundRect(CARD, 20));

        TextView title = text("Page transition blur", 17, TEXT, true);
        title.setPadding(dp(6), dp(4), dp(6), dp(10));
        container.addView(title, matchWrap());

        String current = getBlurLevelLabel();
        for (int i = 0; i < values.length; i++) {
            String value = values[i];
            if (i > 0) addDivider(container);
            LinearLayout option = new LinearLayout(mActivity);
            option.setGravity(Gravity.CENTER_VERTICAL);
            option.setPadding(dp(6), 0, dp(6), 0);
            TextView label = text(value, 15, TEXT, false);
            option.addView(label, new LinearLayout.LayoutParams(0, dp(46), 1f));
            RadioButton radio = new RadioButton(mActivity);
            radio.setClickable(false);
            radio.setFocusable(false);
            radio.setButtonTintList(new ColorStateList(
                    new int[][] {
                        new int[] { android.R.attr.state_checked },
                        new int[] {}
                    },
                    new int[] { PRIMARY, SECONDARY }));
            radio.setChecked(value.equals(current));
            option.addView(radio);
            option.setOnClickListener(v -> {
                applyBlurLevel(value);
                dialog.dismiss();
            });
            container.addView(option, matchWrap());
        }

        dialog.setContentView(container);
        Window window = dialog.getWindow();
        if (window != null) {
            window.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
            window.setLayout(dp(300), WindowManager.LayoutParams.WRAP_CONTENT);
        }
        dialog.show();
        if (dialog.getWindow() != null) {
            dialog.getWindow().setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
            dialog.getWindow().setLayout(dp(300), WindowManager.LayoutParams.WRAP_CONTENT);
        }
    }

    private void applyBlurLevel(String selected) {
        String value = "Off".equals(selected) ? "default"
                : selected.toLowerCase(java.util.Locale.ROOT);
        String previous = ContextUtils.getAppSharedPreferences()
                .getString(PREF_BLUR_LEVEL, "medium");
        boolean changed = !value.equals(previous);
        ContextUtils.getAppSharedPreferences().edit()
                .putString(PREF_BLUR_LEVEL, value)
                .putBoolean(PREF_DARKEN,
                        !"default".equals(value)
                                && ContextUtils.getAppSharedPreferences()
                                        .getBoolean(PREF_DARKEN, true))
                .apply();
        if ("default".equals(value)) {
            ContextUtils.getAppSharedPreferences().edit()
                    .putBoolean(PREF_DARKEN, false).apply();
            if (mDarkenSwitch != null) mDarkenSwitch.setChecked(false);
        }
        if (mBlurValue != null) mBlurValue.setText(selected);
        if (mDarkenSwitch != null) mDarkenSwitch.setEnabled(!"default".equals(value));
        if (changed) {
            mRequiresRestart = true;
            if (mBlurRestartHint != null) mBlurRestartHint.setVisibility(View.VISIBLE);
        }
    }

    private void startBrowsingWithFeedback() {
        if (!mCanStartBrowsing || mStartInvoked || mRestartInProgress) return;
        mStartInvoked = true;
        mHandler.removeCallbacks(mPollRunnable);
        mStartButton.setEnabled(false);

        if (!mRequiresRestart) {
            mListener.onStartBrowsing();
            return;
        }

        mRestartInProgress = true;
        mStartButton.setText("Restarting");
        mStartButton.setTextColor(PRIMARY_TEXT);

        LayerDrawable background = new LayerDrawable(new Drawable[] {
            roundRect(PRIMARY, 28),
            new ClipDrawable(roundRect(Color.rgb(168, 183, 248), 28),
                    Gravity.LEFT, ClipDrawable.HORIZONTAL)
        });
        ClipDrawable progress = (ClipDrawable) background.getDrawable(1);
        progress.setLevel(0);
        mStartButton.setBackground(background);

        ValueAnimator animator = ValueAnimator.ofInt(0, 10000);
        animator.setDuration(1000);
        animator.setInterpolator(new LinearInterpolator());
        animator.addUpdateListener(animation ->
                progress.setLevel((Integer) animation.getAnimatedValue()));
        animator.addListener(new AnimatorListenerAdapter() {
            @Override
            public void onAnimationEnd(Animator animation) {
                // Mark first-run complete without launching a second Activity.
                // Chromium's lifetime controller will relaunch the app itself.
                mListener.onPrepareForRestart();
                mRoot.animate()
                        .alpha(0f)
                        .setDuration(280)
                        .setInterpolator(new AccelerateDecelerateInterpolator())
                        .withEndAction(BraveRelaunchUtils::restart)
                        .start();
            }
        });
        animator.start();
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

    private boolean isBlurTransitionEnabled() {
        return !"default".equals(ContextUtils.getAppSharedPreferences()
                .getString(PREF_BLUR_LEVEL, "medium"));
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
        boolean allFiltersReady = total == REQUIRED_FILTER_COUNT
                && downloaded == REQUIRED_FILTER_COUNT;
        mCanStartBrowsing = ready && allFiltersReady;
        mEngineState.setText(mCanStartBrowsing
                ? "✓   Ad blocker engine: Ready with all 29 filters"
                : (allFiltersReady
                    ? "○   Ad blocker engine: Activating with 29 filters"
                    : "○   Ad blocker engine: Waiting for all 29 filters"));
        mEngineState.setTextColor(mCanStartBrowsing ? SUCCESS : SECONDARY);
        mProtectionTitle.setText(mCanStartBrowsing
                ? "Ad-blocking protection completed"
                : "Preparing ad-blocking protection...");
        mProtectionTitle.setTextColor(mCanStartBrowsing ? SUCCESS : TEXT);
        mProtectionSubtitle.setText(mCanStartBrowsing
                ? "All 29 filters are loaded and active"
                : "Engine starts after the first successful filter download");
        mProtectionSubtitle.setTextColor(mCanStartBrowsing ? SUCCESS : SECONDARY);
        mProtectionSpinner.setText(mCanStartBrowsing ? "✓" : "⟳");
        mProtectionSpinner.setTextColor(mCanStartBrowsing ? SUCCESS : PRIMARY);
        mProgress.setProgressTintList(ColorStateList.valueOf(
                mCanStartBrowsing ? SUCCESS : PRIMARY));
        mPercent.setTextColor(mCanStartBrowsing ? SUCCESS : TEXT);
        mFilterCount.setText("Filters: " + downloaded + " of " + REQUIRED_FILTER_COUNT + " loaded");
        mFilterCount.setTextColor(allFiltersReady ? SUCCESS : SECONDARY);
        mFinalizing.setText(mCanStartBrowsing
                ? "✓   Finalizing: All filter rules applied"
                : (allFiltersReady
                    ? "○   Finalizing: Activating the native engine..."
                    : "○   Finalizing: Downloading remaining filters..."));
        mFinalizing.setTextColor(mCanStartBrowsing ? SUCCESS : SECONDARY);
        mStartButton.setEnabled(mCanStartBrowsing && !mStartInvoked);
        if (!mRestartInProgress) {
            mStartButton.setText("Start browsing");
            mStartButton.setTextColor(mCanStartBrowsing ? PRIMARY_TEXT : DISABLED_BUTTON_TEXT);
            mStartButton.setBackground(roundRect(
                    mCanStartBrowsing ? PRIMARY : DISABLED_BUTTON, 28));
        }
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
        return text(value, originalSizeSp * 0.88f, color, bold);
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
