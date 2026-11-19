/* Copyright (c) 2026 The Sandium Authors. All rights reserved.
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at https://mozilla.org/MPL/2.0/. */

package org.chromium.chrome.browser.firstrun;

import android.animation.ValueAnimator;
import android.app.Activity;
import android.app.Dialog;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.ClipDrawable;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.LayerDrawable;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.ForegroundColorSpan;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.Window;
import android.view.WindowManager;
import android.view.View;
import android.view.ViewGroup;
import android.view.animation.LinearInterpolator;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ImageView;
import android.widget.ProgressBar;
import android.widget.RadioButton;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Switch;

import org.chromium.base.BraveFeatureList;
import org.chromium.base.ContextUtils;
import org.chromium.brave_shields.mojom.FilterListAndroidHandler;
import org.chromium.brave_shields.mojom.SubscriptionInfo;
import org.chromium.chrome.R;
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

    // Welcome is intentionally always dark, independent of the device's day theme.
    // Use the default dark Shields surface; leave its existing charcoal cards and accents alone.
    private static final int BACKGROUND = Color.rgb(15, 12, 19);
    private static final int CARD = Color.rgb(26, 26, 26);
    private static final int SEPARATOR = Color.rgb(69, 69, 69);
    private static final int PRIMARY = Color.rgb(25, 140, 255);
    // Approved off-white ready state and pale-green progress fill.
    private static final int START_BUTTON = Color.rgb(238, 236, 229);
    // Start and restart share the same 1.5-second feedback without changing layout.
    private static final int START_TRACK = Color.rgb(238, 236, 229);
    private static final int START_PROGRESS = Color.rgb(182, 220, 193);
    private static final int PRIMARY_TEXT = Color.rgb(8, 15, 24);
    private static final int DISABLED_BUTTON = Color.rgb(55, 55, 55);
    private static final int DISABLED_BUTTON_TEXT = Color.rgb(160, 160, 160);
    private static final int TEXT = Color.rgb(250, 250, 250);
    private static final int SECONDARY = Color.rgb(189, 189, 189);
    private static final int SUCCESS = Color.rgb(70, 200, 120);
    // Decorative category colors sampled from the owner's Oppo Settings reference.
    // These do not encode switch state, warnings or native protection readiness.
    private static final int ICON_GREEN = Color.rgb(2, 190, 18);
    private static final int ICON_AMBER = Color.rgb(253, 178, 0);
    private static final int ICON_ORANGE = Color.rgb(255, 119, 1);

    private static final String PREF_NATIVE_BLUR = "sandium_page_transition_blur_enabled";
    private static final String PREF_BLUR_LEVEL = "sandium_page_transition_blur_level";
    private static final String PREF_DARKEN = "sandium_page_transition_darken";
    private static final String PREF_ENGINE_READY = "sandium.ad_block.engine_warmup_done_v2";

    private final Activity mActivity;
    private final Listener mListener;
    private final Handler mHandler = new Handler(Looper.getMainLooper());
    private final List<Switch> mSwitches = new ArrayList<>();
    private final Runnable mPollRunnable = this::pollFilterStatus;

    private LinearLayout mRoot;
    private LinearLayout mContent;
    private ScrollView mScrollView;
    private LinearLayout mAdvancedOptions;
    private LinearLayout mMainSettingsCard;
    private final List<LinearLayout> mMainSettingGroups = new ArrayList<>();
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
    private org.chromium.chrome.browser.privacy.secure_dns.SandiumSecureDnsDropdown mSecureDns;
    private boolean mExpanded;
    private boolean mDestroyed;
    private boolean mPollInFlight;
    private boolean mCanStartBrowsing;
    private boolean mRequiresRestart;
    private boolean mRestartInProgress;
    private boolean mStartInvoked;
    private Switch mDarkenSwitch;
    private ClipDrawable mRestartButtonFill;
    private ValueAnimator mRestartAnimator;
    private SandiumShieldsTracer mLogoTracer;
    private final Runnable mRestartRunnable = this::performRestart;

    private static final long START_FEEDBACK_MS = 1500L;
    private boolean mCompletionDispatched;
    private boolean mNotificationsEnabled = true;
    private boolean mPendingRestart;
    private long mStartFeedbackAt;
    private int mDotPhase;
    private final Runnable mDotsRunnable = this::updatePreparingDots;
    private final Runnable mCountdownRunnable = this::updateStartCountdown;

    private void performRestart() {
        if (mDestroyed || !mRestartInProgress || mCompletionDispatched) return;
        if (!persistNotificationSetup()) {
            cancelButtonFeedback();
            for (Switch toggle : mSwitches) toggle.setEnabled(true);
            if (mDarkenSwitch != null) mDarkenSwitch.setEnabled(isBlurTransitionEnabled());
            updateStartButtonState();
            android.widget.Toast.makeText(mActivity, R.string.sandium_welcome_save_failed,
                    android.widget.Toast.LENGTH_LONG).show();
            if (mFilterHandler != null) pollFilterStatus();
            return;
        }
        mCompletionDispatched = true;
        mHandler.removeCallbacks(mCountdownRunnable);
        if (mPendingRestart) {
            mListener.onPrepareForRestart();
            BraveRelaunchUtils.restart();
        } else {
            mListener.onStartBrowsing();
        }
    }

    // The next activity/process must see this before startup can request permission.
    @android.annotation.SuppressLint("ApplySharedPref")
    private boolean persistNotificationSetup() {
        android.content.SharedPreferences prefs = mActivity.getApplicationContext()
                .getSharedPreferences("sandium_notifications", android.content.Context.MODE_PRIVATE);
        return prefs.edit().putBoolean("enabled", mNotificationsEnabled)
                .putBoolean("setup_completed", true)
                .putBoolean("request_pending",
                        mNotificationsEnabled && !prefs.getBoolean("request_attempted", false))
                .commit();
    }

    private String readyButtonLabel() {
        return mActivity.getString(mRequiresRestart
                ? R.string.sandium_welcome_quick_restart : R.string.sandium_welcome_start);
    }

    private void updatePreparingDots() {
        mHandler.removeCallbacks(mDotsRunnable);
        if (mDestroyed || mCanStartBrowsing || mStartInvoked
                || !mStartButton.isAttachedToWindow()) return;
        SpannableString dots = new SpannableString(
                mActivity.getString(R.string.sandium_welcome_dots));
        for (int i = 0; i < 3; i++) {
            int color = !ValueAnimator.areAnimatorsEnabled() || i == mDotPhase
                    ? DISABLED_BUTTON_TEXT : Color.rgb(95, 95, 95);
            dots.setSpan(new ForegroundColorSpan(color), i * 2, i * 2 + 1,
                    Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        }
        mStartButton.setText(dots);
        mStartButton.setContentDescription(
                mActivity.getString(R.string.sandium_welcome_protection_preparing));
        mDotPhase = (mDotPhase + 1) % 3;
        if (ValueAnimator.areAnimatorsEnabled()) mHandler.postDelayed(mDotsRunnable, 300);
    }

    private void updateStartCountdown() {
        mHandler.removeCallbacks(mCountdownRunnable);
        if (mDestroyed || !mRestartInProgress || mCompletionDispatched) return;
        long elapsed = Math.max(0, SystemClock.uptimeMillis() - mStartFeedbackAt);
        int remaining = Math.max(1, 5 - (int) (elapsed / 300));
        mStartButton.setText(mActivity.getString(mPendingRestart
                ? R.string.sandium_welcome_restarting_countdown
                : R.string.sandium_welcome_starting_countdown, remaining));
        if (elapsed < START_FEEDBACK_MS) {
            mHandler.postDelayed(mCountdownRunnable, 300 - elapsed % 300);
        }
    }

    private void cancelButtonFeedback() {
        mHandler.removeCallbacks(mDotsRunnable);
        mHandler.removeCallbacks(mCountdownRunnable);
        mHandler.removeCallbacks(mRestartRunnable);
        if (mRestartAnimator != null) mRestartAnimator.cancel();
        if (!mCompletionDispatched) {
            mRestartInProgress = false;
            mStartInvoked = false;
        }
    }

    private void updateStartButtonState() {
        if (mDestroyed || mRestartInProgress || mCompletionDispatched) return;
        mHandler.removeCallbacks(mDotsRunnable);
        mStartButton.setEnabled(mCanStartBrowsing && !mStartInvoked);
        mStartButton.setTextColor(mCanStartBrowsing ? PRIMARY_TEXT : DISABLED_BUTTON_TEXT);
        mStartButton.setBackgroundTintList(null);
        mStartButton.setBackground(roundRect(
                mCanStartBrowsing ? START_BUTTON : DISABLED_BUTTON, 28));
        if (mCanStartBrowsing) {
            mStartButton.setText(readyButtonLabel());
            mStartButton.setContentDescription(readyButtonLabel());
        } else {
            mStartButton.setText(mActivity.getString(R.string.sandium_welcome_dots));
            updatePreparingDots();
        }
    }

    SandiumWelcomeSetupView(Activity activity, Listener listener) {
        mActivity = activity;
        mListener = listener;
    }

    View createView() {
        // Android 15 may enforce a transparent status bar. Its backing must be
        // the same dark surface as this screen, not the Activity theme's launch colour.
        // Leave safe-inset/layout ownership with the first-run Activity.
        mActivity.getWindow().setBackgroundDrawable(new ColorDrawable(BACKGROUND));
        mActivity.getWindow().setStatusBarColor(BACKGROUND);
        mActivity.getWindow().setNavigationBarColor(BACKGROUND);
        View decor = mActivity.getWindow().getDecorView();
        decor.setSystemUiVisibility(decor.getSystemUiVisibility()
                & ~(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
                        | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR));
        mRoot = new LinearLayout(mActivity);
        mRoot.setOrientation(LinearLayout.VERTICAL);
        mRoot.setBackgroundColor(BACKGROUND);

        // Keep the existing content anchored at the top. The content only extends
        // downward when More options is opened; the ScrollView handles overflow
        // without vertically recentering or shifting the current screen.
        mScrollView = new ScrollView(mActivity);
        mScrollView.setFillViewport(true);
        mScrollView.setVerticalScrollBarEnabled(false);
        mScrollView.setHorizontalScrollBarEnabled(false);
        mScrollView.setOverScrollMode(View.OVER_SCROLL_NEVER);
        mScrollView.setClipToPadding(false);
        mRoot.addView(mScrollView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        mContent = new LinearLayout(mActivity);
        mContent.setOrientation(LinearLayout.VERTICAL);
        mContent.setPadding(dp(18), dp(6), dp(18), dp(4));
        mContent.setGravity(Gravity.TOP);
        mScrollView.addView(mContent, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        buildBrandCard();

        buildFilterProgressCard();
        buildMainSettingsCard();

        LinearLayout buttonContainer = new LinearLayout(mActivity);
        buttonContainer.setOrientation(LinearLayout.VERTICAL);
        buttonContainer.setGravity(Gravity.CENTER);
        buttonContainer.setPadding(dp(18), dp(8), dp(18), dp(12));
        mRoot.addView(buttonContainer, matchWrap());

        mStartButton = new Button(mActivity);
        mStartButton.setText(mActivity.getString(R.string.sandium_welcome_dots));
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
        mStartButton.addOnAttachStateChangeListener(new View.OnAttachStateChangeListener() {
            @Override
            public void onViewAttachedToWindow(View view) {
                if (mDestroyed || mCompletionDispatched) return;
                updateStartButtonState();
                for (Switch toggle : mSwitches) toggle.setEnabled(mProfile != null);
                if (mDarkenSwitch != null) {
                    mDarkenSwitch.setEnabled(mProfile != null && isBlurTransitionEnabled());
                }
                if (mFilterHandler != null) pollFilterStatus();
            }
            @Override
            public void onViewDetachedFromWindow(View view) {
                cancelButtonFeedback();
            }
        });
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(52));
        buttonContainer.addView(mStartButton, buttonParams);

        fadeIn(mContent);
        return mRoot;
    }

    void initialize(Profile profile) {
        mProfile = profile;
        if (mSecureDns != null) mSecureDns.finishNativeStartup();
        applyInitialPreferences();
        initializeSearchEngine();
        for (Switch toggle : mSwitches) toggle.setEnabled(true);
        if (mDarkenSwitch != null) mDarkenSwitch.setEnabled(isBlurTransitionEnabled());
        mFilterHandler = FilterListServiceFactory.getInstance()
                .getFilterListAndroidHandler(profile, null);
        // Queue the native warm-up immediately. Native code waits for the actual
        // enabled subscriptions, then marks ready only after the additional engine loads.
        FilterListServiceFactory.requestSandiumHomepageWarmup(profile);
        pollFilterStatus();
    }

    void destroy() {
        mDestroyed = true;
        cancelButtonFeedback();
        mHandler.removeCallbacks(mRestartRunnable);
        if (mRestartAnimator != null) mRestartAnimator.cancel();
        if (mLogoTracer != null) mLogoTracer.setEnabled(false);
        if (mContent != null) { mContent.animate().cancel(); mContent.setAlpha(1f); }
        if (mAdvancedOptions != null) {
            mAdvancedOptions.animate().cancel(); mAdvancedOptions.setAlpha(1f);
        }
        mHandler.removeCallbacks(mPollRunnable);
        mFilterHandler = null;
    }

    // App-owned content only; never delay input or change native switch animation.
    private void fadeIn(View view) {
        if (!ValueAnimator.areAnimatorsEnabled()) return;
        view.animate().cancel();
        view.setAlpha(0f);
        view.post(() -> {
            if (!mDestroyed && view.isAttachedToWindow()
                    && view.getVisibility() == View.VISIBLE && ValueAnimator.areAnimatorsEnabled()) {
                view.animate().alpha(1f).setDuration(120).setStartDelay(0)
                        .setInterpolator(new LinearInterpolator()).start();
            } else {
                view.setAlpha(1f);
            }
        });
    }

    // Persist setup values before the native-feature relaunch.
    @android.annotation.SuppressLint("ApplySharedPref")
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
        if (!preferences.contains(PREF_NATIVE_BLUR)) {
            editor.putBoolean(PREF_NATIVE_BLUR, isBlurTransitionEnabled());
        }
        if (!preferences.contains(PREF_DARKEN)) editor.putBoolean(PREF_DARKEN, true);
        editor.commit();
        // Brave feature overrides are read during native startup; relaunch after
        // completing first run so the selected Night Mode is actually active.
        BraveFeatureUtil.enableFeature(BraveFeatureList.ENABLE_FORCE_DARK, true, true);
        mRequiresRestart = true;
    }

    private void buildBrandCard() {
        // Oppo profile-card arrangement, using the exact existing Sandium asset.
        // This is an informational brand header, not a fake account/sign-in button.
        LinearLayout brand = new LinearLayout(mActivity);
        brand.setOrientation(LinearLayout.HORIZONTAL);
        brand.setGravity(Gravity.CENTER_VERTICAL);
        brand.setPadding(dp(16), dp(8), dp(16), dp(8));
        brand.setBackground(roundRect(CARD, 24));

        ImageView logo = new ImageView(mActivity);
        mLogoTracer = new SandiumShieldsTracer(logo);
        logo.setImageDrawable(mLogoTracer);
        mLogoTracer.setEnabled(true);
        logo.setScaleType(ImageView.ScaleType.FIT_CENTER);
        logo.setPadding(dp(8), dp(8), dp(8), dp(8));
        logo.setBackground(roundRect(Color.rgb(36, 36, 36), 28));
        // No crop or tint: preserve every part and color of the original artwork.
        logo.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        brand.addView(logo, new LinearLayout.LayoutParams(dp(56), dp(56)));

        LinearLayout labels = new LinearLayout(mActivity);
        labels.setOrientation(LinearLayout.VERTICAL);
        labels.setPaddingRelative(dp(14), 0, 0, 0);
        brand.addView(labels, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        TextView title = text("Sandium", 24, TEXT, true);
        title.setAccessibilityHeading(true);
        labels.addView(title, matchWrap());
        TextView subtitle = text("Choose your browsing preferences.", 13, SECONDARY, false);
        subtitle.setPadding(0, dp(4), 0, 0);
        subtitle.setLineSpacing(0, 1f);
        // Wrap naturally; extreme font scales retain accessibility overflow rather than clip.
        labels.addView(subtitle, matchWrap());
        LinearLayout.LayoutParams params = matchWrap();
        params.bottomMargin = dp(8);
        mContent.addView(brand, params);
    }

    // This switch can be followed immediately by restart; persist synchronously.
    @android.annotation.SuppressLint("ApplySharedPref")
    private void persistDarkenPreference(boolean checked) {
        ContextUtils.getAppSharedPreferences().edit().putBoolean(PREF_DARKEN, checked).commit();
    }

    private void buildMainSettingsCard() {
        LinearLayout card = card();
        mMainSettingsCard = card;
        LinearLayout.LayoutParams cardParams = matchWrap();
        cardParams.weight = 1f;
        mContent.addView(card, cardParams);

        addSwitchRow(card, "⬡", "Block trackers & ads",
                "Block ads and trackers",
                true, checked -> setProtectionEnabled(checked));
        addSettingsDivider(card);

        addRestartSwitchRow(card, "☾", "Night Mode",
                "Force dark mode for web content",
                true, checked -> {
                    BraveFeatureUtil.enableFeature(BraveFeatureList.ENABLE_FORCE_DARK, checked, true);
                    mRequiresRestart = true;
                });
        addSettingsDivider(card);

        addBlurRow(card);
        addSettingsDivider(card);

        boolean blurEnabled = isBlurTransitionEnabled();
        boolean darkenChecked = blurEnabled && ContextUtils.getAppSharedPreferences()
                .getBoolean(PREF_DARKEN, true);
        mDarkenSwitch = addRestartSwitchRow(card, "◐", "Darken transition",
                "Dim the outgoing page",
                darkenChecked, checked -> {
                    if (!isBlurTransitionEnabled()) return;
                    persistDarkenPreference(checked);
                    mRequiresRestart = true;
                });
        mDarkenSwitch.setEnabled(blurEnabled);
        addSettingsDivider(card);

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
            updateSettingsStretch();
            mAdvancedOptions.animate().cancel(); mAdvancedOptions.setAlpha(1f);
            mAdvancedOptions.setVisibility(mExpanded ? View.VISIBLE : View.GONE);
            if (mExpanded) fadeIn(mAdvancedOptions);
            else mScrollView.post(() -> mScrollView.scrollTo(0, 0));
            mMoreOptionsLabel.setText(mExpanded ? mActivity.getString(R.string.sandium_welcome_fewer_options) : mActivity.getString(R.string.sandium_welcome_more_options));
            arrow.setText(mExpanded ? mActivity.getString(R.string.sandium_welcome_expanded_glyph) : mActivity.getString(R.string.sandium_welcome_collapsed_glyph));
        });
        card.addView(more, matchWrap());

        mAdvancedOptions = new LinearLayout(mActivity);
        mAdvancedOptions.setOrientation(LinearLayout.VERTICAL);
        mAdvancedOptions.setVisibility(View.GONE);
        card.addView(mAdvancedOptions, matchWrap());
        // Optional DNS belongs to the existing GONE section. The main settings card
        // gains no row, spacer or margin until the user opens More options.
        addSettingsDivider(mAdvancedOptions);
        mSecureDns = new org.chromium.chrome.browser.privacy.secure_dns.SandiumSecureDnsDropdown(
                mActivity, false, false);
        mSecureDns.setColors(TEXT, SECONDARY, CARD, PRIMARY);
        mAdvancedOptions.addView(mSecureDns, matchWrap());
        mNotificationsEnabled = mActivity.getApplicationContext()
                .getSharedPreferences("sandium_notifications", android.content.Context.MODE_PRIVATE)
                .getBoolean("enabled", true);
        addSettingsDivider(mAdvancedOptions);
        addSwitchRow(mAdvancedOptions, "♧",
                mActivity.getString(R.string.sandium_welcome_notifications),
                mActivity.getString(R.string.sandium_welcome_notifications_summary),
                mNotificationsEnabled, checked -> mNotificationsEnabled = checked);
        addSettingsDivider(mAdvancedOptions);
        addSwitchRow(mAdvancedOptions, "◈", "Block third-party cookies",
                "Prevent third-party sites from storing cookies",
                false, checked -> {
                    BraveShieldsContentSettings.setShieldsValue(
                            mProfile, "", BraveShieldsContentSettings.RESOURCE_IDENTIFIER_COOKIES,
                            checked ? BraveShieldsContentSettings.BLOCK_THIRDPARTY_RESOURCE
                                    : BraveShieldsContentSettings.DEFAULT,
                            false);
                });
        addSettingsDivider(mAdvancedOptions);
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
        params.setMargins(0, 0, 0, dp(8));
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
                "Waiting for downloads and native engine",
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
        mProgress.setProgressTintList(ColorStateList.valueOf(SUCCESS));
        mProgress.setProgressBackgroundTintList(ColorStateList.valueOf(Color.rgb(62, 62, 62)));
        progressRow.addView(mProgress, new LinearLayout.LayoutParams(0, dp(5), 1f));

        mPercent = text("0%", 11, TEXT, false);
        mPercent.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams percentParams = new LinearLayout.LayoutParams(dp(38), dp(22));
        percentParams.setMargins(dp(8), 0, 0, 0);
        progressRow.addView(mPercent, percentParams);

        View divider = new View(mActivity);
        divider.setBackgroundColor(Color.rgb(69, 69, 69));
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

    // The fill-viewport pass has surplus height only when natural content fits.
    // Distribute that surplus between complete setting groups, keeping each
    // description and restart hint together. Never scale text or force a height.
    private LinearLayout addSettingGroup(LinearLayout parent) {
        LinearLayout group = new LinearLayout(mActivity);
        group.setOrientation(LinearLayout.VERTICAL);
        group.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams params = matchWrap();
        if (parent == mMainSettingsCard) {
            params.weight = mExpanded ? 0f : 1f;
            mMainSettingGroups.add(group);
        }
        parent.addView(group, params);
        return group;
    }

    private void updateSettingsStretch() {
        float weight = mExpanded ? 0f : 1f;
        LinearLayout.LayoutParams cardParams =
                (LinearLayout.LayoutParams) mMainSettingsCard.getLayoutParams();
        cardParams.weight = weight;
        mMainSettingsCard.setLayoutParams(cardParams);
        for (LinearLayout group : mMainSettingGroups) {
            LinearLayout.LayoutParams params =
                    (LinearLayout.LayoutParams) group.getLayoutParams();
            params.weight = weight;
            group.setLayoutParams(params);
        }
    }

    private void addBlurRow(LinearLayout parent) {
        LinearLayout group = addSettingGroup(parent);
        LinearLayout row = new LinearLayout(mActivity);
        row.setGravity(Gravity.TOP);
        row.setPadding(dp(16), dp(12), dp(14), dp(2));
        group.addView(row, matchWrap());

        TextView icon = text("▱", 23, PRIMARY, false);
        icon.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams iconParams = new LinearLayout.LayoutParams(dp(38), dp(38));
        iconParams.topMargin = dp(2);
        row.addView(icon, iconParams);

        LinearLayout labels = new LinearLayout(mActivity);
        labels.setOrientation(LinearLayout.VERTICAL);
        labels.setPadding(dp(6), 0, dp(8), 0);
        row.addView(labels, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        TextView blurTitle = itemText("Page transition blur", 16, TEXT, false);
        blurTitle.setSingleLine(true);
        labels.addView(blurTitle, matchWrap());

        TextView summary = itemText(
                mActivity.getString(R.string.sandium_welcome_native_blur_summary),
                13, SECONDARY, false);
        summary.setPadding(0, dp(3), dp(4), 0);
        labels.addView(summary, matchWrap());

        mBlurRestartHint = text("↻  Needs a quick restart to apply", 11, PRIMARY, false);
        mBlurRestartHint.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        mBlurRestartHint.setLetterSpacing(0.01f);
        mBlurRestartHint.setPadding(dp(60), 0, dp(14), dp(4));
        mBlurRestartHint.setVisibility(View.VISIBLE);

        LinearLayout selector = new LinearLayout(mActivity);
        selector.setGravity(Gravity.CENTER_VERTICAL);
        selector.setPadding(dp(6), 0, dp(6), 0);
        selector.setBackground(outlinedRoundRect(CARD, PRIMARY, 28));
        // Balance the end chevron so On/Off stays at the pill's exact centre in LTR and RTL.
        View chevronBalance = new View(mActivity);
        chevronBalance.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        selector.addView(chevronBalance, new LinearLayout.LayoutParams(dp(16), dp(38)));
        mBlurValue = text(getBlurLevelLabel(), 14, TEXT, false);
        mBlurValue.setSingleLine(true);
        mBlurValue.setGravity(Gravity.CENTER);
        mBlurValue.setEllipsize(android.text.TextUtils.TruncateAt.END);
        selector.addView(mBlurValue, new LinearLayout.LayoutParams(0, dp(44), 1f));
        TextView chevron = text("▾", 15, PRIMARY, false);
        chevron.setGravity(Gravity.CENTER);
        selector.addView(chevron, new LinearLayout.LayoutParams(dp(16), dp(38)));
        selector.setOnClickListener(v -> showBlurLevelPicker());
        LinearLayout.LayoutParams selectorParams =
                new LinearLayout.LayoutParams(dp(112), dp(40));
        selectorParams.setMargins(dp(4), dp(1), 0, 0);
        row.addView(selector, selectorParams);
        group.addView(mBlurRestartHint, matchWrap());
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
        LinearLayout group = addSettingGroup(parent);
        LinearLayout row = new LinearLayout(mActivity);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(16), dp(5), dp(14), dp(5));
        group.addView(row, matchWrap());

        TextView icon = text(glyph, 23, welcomeIconColor(glyph), false);
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
        restartHint.setPadding(dp(56), 0, dp(14), dp(4));
        restartHint.setVisibility(showRestartHint && checked ? View.VISIBLE : View.GONE);
        if (showRestartHint) group.addView(restartHint, matchWrap());

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
                    Color.WHITE,
                    Color.rgb(232, 232, 232),
                    Color.rgb(84, 84, 84),
                    Color.rgb(133, 133, 133)
                }));
        toggle.setTrackTintList(new ColorStateList(
                new int[][] {
                    new int[] { android.R.attr.state_enabled, android.R.attr.state_checked },
                    new int[] { android.R.attr.state_enabled },
                    new int[] { android.R.attr.state_checked },
                    new int[] {}
                },
                new int[] {
                    Color.rgb(25, 140, 255), // Fixed Oppo switch palette, even with dynamic colors.
                    Color.rgb(80, 80, 80),
                    Color.rgb(145, 145, 145),
                    Color.rgb(63, 63, 63)
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
        switch (getSandiumBlurLevel()) {
            case "off": return mActivity.getString(R.string.sandium_welcome_off);
            case "medium": return mActivity.getString(R.string.sandium_welcome_blur_medium);
            case "high": return mActivity.getString(R.string.sandium_welcome_blur_high);
            default: return mActivity.getString(R.string.sandium_welcome_blur_low);
        }
    }

    private static String getSandiumBlurLevel() {
        android.content.SharedPreferences prefs = ContextUtils.getAppSharedPreferences();
        String choice = prefs.getString("sandium_page_transition_blur_choice", "");
        if ("off".equals(choice) || "low".equals(choice)
                || "medium".equals(choice) || "high".equals(choice)) return choice;
        if (prefs.contains("sandium_page_transition_blur_enabled")) {
            return prefs.getBoolean("sandium_page_transition_blur_enabled", true) ? "low" : "off";
        }
        String legacy = prefs.getString("sandium_page_transition_blur_level", "on");
        return "default".equals(legacy) || "off".equals(legacy) ? "off" : "low";
    }


    private void showBlurLevelPicker() {
        final String[] values = { mActivity.getString(R.string.sandium_welcome_off),
                mActivity.getString(R.string.sandium_welcome_blur_low),
                mActivity.getString(R.string.sandium_welcome_blur_medium),
                mActivity.getString(R.string.sandium_welcome_blur_high) };
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

    // A restart can follow immediately, so persist the startup-only choice first.
    @android.annotation.SuppressLint("ApplySharedPref")
    private void applyBlurLevel(String selected) {
        String level;
        if (mActivity.getString(R.string.sandium_welcome_off).equals(selected)) level = "off";
        else if (mActivity.getString(R.string.sandium_welcome_blur_low).equals(selected)) level = "low";
        else if (mActivity.getString(R.string.sandium_welcome_blur_medium).equals(selected)) level = "medium";
        else if (mActivity.getString(R.string.sandium_welcome_blur_high).equals(selected)) level = "high";
        else return;
        boolean enabled = !"off".equals(level);
        boolean changed = !level.equals(getSandiumBlurLevel());
        if (!ContextUtils.getAppSharedPreferences().edit()
                .putString("sandium_page_transition_blur_choice", level)
                .putBoolean(PREF_NATIVE_BLUR, enabled).commit()) {
            android.widget.Toast.makeText(mActivity, R.string.sandium_welcome_save_failed,
                    android.widget.Toast.LENGTH_LONG).show();
            return;
        }
        if (mBlurValue != null) mBlurValue.setText(getBlurLevelLabel());
        if (mDarkenSwitch != null) mDarkenSwitch.setEnabled(enabled);
        if (changed) {
            mRequiresRestart = true;
            if (mBlurRestartHint != null) mBlurRestartHint.setVisibility(View.VISIBLE);
            updateStartButtonState();
        }
    }

    private void startBrowsingWithFeedback() {
        if (mDestroyed || !mCanStartBrowsing || mStartInvoked || mRestartInProgress
                || mCompletionDispatched) return;
        mStartInvoked = true;
        mRestartInProgress = true;
        mPendingRestart = mRequiresRestart;
        mHandler.removeCallbacks(mPollRunnable);
        mHandler.removeCallbacks(mDotsRunnable);
        mStartButton.setEnabled(false);
        mStartButton.setTextColor(PRIMARY_TEXT);
        mRestartButtonFill = new ClipDrawable(
                roundRect(START_PROGRESS, 28), Gravity.START, ClipDrawable.HORIZONTAL);
        mRestartButtonFill.setLevel(0);
        mStartButton.setBackgroundTintList(null);
        mStartButton.setBackground(new LayerDrawable(new Drawable[] {
                roundRect(START_TRACK, 28), mRestartButtonFill}));
        mStartButton.setContentDescription(readyButtonLabel());
        mStartFeedbackAt = SystemClock.uptimeMillis();
        updateStartCountdown();
        if (ValueAnimator.areAnimatorsEnabled()) {
            mRestartAnimator = ValueAnimator.ofInt(0, 10000);
            mRestartAnimator.setDuration(START_FEEDBACK_MS);
            mRestartAnimator.setInterpolator(new LinearInterpolator());
            mRestartAnimator.addUpdateListener(animation ->
                    mRestartButtonFill.setLevel((Integer) animation.getAnimatedValue()));
            mRestartAnimator.start();
        } else {
            mRestartButtonFill.setLevel(10000);
        }
        for (Switch toggle : mSwitches) toggle.setEnabled(false);
        // Completion is clock-driven, not animation-driven, and fires exactly once.
        mHandler.postDelayed(mRestartRunnable, START_FEEDBACK_MS);
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
        return !"off".equals(getSandiumBlurLevel());
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
                if (subscriptions == null) {
                    mPollInFlight = false;
                    updateEngineStatus(false, 0, 0);
                    mFinalizing.setText(mActivity.getString(R.string.sandium_welcome_status_retry));
                    schedulePoll();
                    return;
                }
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
            updateEngineStatus(false, 0, 0);
            mFinalizing.setText(mActivity.getString(R.string.sandium_welcome_status_retry));
            schedulePoll();
        }
    }

    // Count the selected subscriptions, not a build-time default-list constant.
    // Keep the native activation signal: downloads alone do not prove readiness.
    static boolean allEnabledFiltersDownloaded(int downloaded, int total) {
        return total > 0 && downloaded == total;
    }

    static boolean canStartWithProtection(boolean ready, int downloaded, int total) {
        return ready && allEnabledFiltersDownloaded(downloaded, total);
    }

    private void updateEngineStatus(boolean ready, int downloaded, int total) {
        int percent = total == 0 ? 0 : Math.min(100, (downloaded * 100) / total);
        mProgress.setProgress(percent);
        mPercent.setText(mActivity.getString(R.string.sandium_welcome_percent, percent));
        boolean allFiltersReady = allEnabledFiltersDownloaded(downloaded, total);
        mCanStartBrowsing = canStartWithProtection(ready, downloaded, total);
        mEngineState.setText(mCanStartBrowsing
                ? mActivity.getString(R.string.sandium_welcome_engine_ready)
                : (allFiltersReady
                    ? mActivity.getString(R.string.sandium_welcome_engine_activating)
                    : mActivity.getString(R.string.sandium_welcome_engine_waiting)));
        mEngineState.setTextColor(mCanStartBrowsing ? SUCCESS : SECONDARY);
        mProtectionTitle.setText(mCanStartBrowsing
                ? mActivity.getString(R.string.sandium_welcome_protection_complete)
                : mActivity.getString(R.string.sandium_welcome_protection_preparing));
        mProtectionTitle.setTextColor(mCanStartBrowsing ? SUCCESS : TEXT);
        mProtectionSubtitle.setText(mCanStartBrowsing
                ? mActivity.getString(R.string.sandium_welcome_downloads_ready)
                : mActivity.getString(R.string.sandium_welcome_downloads_waiting));
        mProtectionSubtitle.setTextColor(mCanStartBrowsing ? SUCCESS : SECONDARY);
        mProtectionSpinner.setText(mCanStartBrowsing ? mActivity.getString(R.string.sandium_welcome_ready_glyph) : mActivity.getString(R.string.sandium_welcome_waiting_glyph));
        mProtectionSpinner.setTextColor(mCanStartBrowsing ? SUCCESS : PRIMARY);
        mProgress.setProgressTintList(ColorStateList.valueOf(
                SUCCESS));
        mPercent.setTextColor(mCanStartBrowsing ? SUCCESS : TEXT);
        mFilterCount.setText(mActivity.getString(allFiltersReady ? R.string.sandium_welcome_filters_ready : R.string.sandium_welcome_filters_waiting, downloaded, total));
        mFilterCount.setTextColor(allFiltersReady ? SUCCESS : SECONDARY);
        mFinalizing.setText(mCanStartBrowsing
                ? mActivity.getString(R.string.sandium_welcome_final_complete)
                : (allFiltersReady
                    ? mActivity.getString(R.string.sandium_welcome_final_activating)
                    : (total == 0
                        ? mActivity.getString(R.string.sandium_welcome_subscriptions_waiting)
                        : mActivity.getString(R.string.sandium_welcome_downloads_remaining))));
        mFinalizing.setTextColor(mCanStartBrowsing ? SUCCESS : SECONDARY);
        updateStartButtonState();
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

    private static int welcomeIconColor(String glyph) {
        switch (glyph) {
            case "⬡": return ICON_GREEN;
            case "☾": return ICON_AMBER;
            case "◐":
            case "◈": return ICON_ORANGE;
            default: return PRIMARY;
        }
    }

    private void addSettingsDivider(LinearLayout parent) {
        View divider = new View(mActivity);
        divider.setBackgroundColor(SEPARATOR);
        LinearLayout.LayoutParams params = matchWrap();
        params.height = dp(1);
        // Align with the label column, leaving the colored icon gutter uninterrupted.
        params.setMarginStart(dp(56));
        params.setMarginEnd(dp(14));
        parent.addView(divider, params);
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

    private GradientDrawable outlinedRoundRect(int fillColor, int strokeColor, int radiusDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fillColor);
        drawable.setCornerRadius(dp(radiusDp));
        drawable.setStroke(dp(1), strokeColor);
        return drawable;
    }

    private int dp(int value) {
        return (int) (value * mActivity.getResources().getDisplayMetrics().density + 0.5f);
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    /** Balanced tracer, sampled from the verified 64 x 77 logo alpha silhouette. */
    private static final class SandiumShieldsTracer extends android.graphics.drawable.Drawable
            implements Runnable, View.OnAttachStateChangeListener,
                    android.view.ViewTreeObserver.OnWindowFocusChangeListener,
                    android.view.ViewTreeObserver.OnGlobalLayoutListener {
        private final android.widget.ImageView mHost;
        private final android.graphics.drawable.Drawable mMark;
        private final android.graphics.Path mOutline = new android.graphics.Path();
        private final android.graphics.Path mScaled = new android.graphics.Path();
        private final android.graphics.Path mSegment = new android.graphics.Path();
        private final android.graphics.PathMeasure mMeasure = new android.graphics.PathMeasure();
        private final android.graphics.Paint mPaint =
                new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        private final android.graphics.Matrix mMatrix = new android.graphics.Matrix();
        private final float[] mImageMatrixValues = new float[9];
        private boolean mEnabled;
        private boolean mListening;
        private int mAlpha = 255;
        private final long mEpoch = android.os.SystemClock.uptimeMillis();

        SandiumShieldsTracer(android.widget.ImageView host) {
            mHost = host;
            mMark = host.getContext().getDrawable(R.drawable.sandium_toolbar_mark).mutate();
            mPaint.setStyle(android.graphics.Paint.Style.STROKE);
            mPaint.setStrokeCap(android.graphics.Paint.Cap.ROUND);
            mPaint.setStrokeJoin(android.graphics.Paint.Join.ROUND);
            mPaint.setColor(0xFF46C878);
            mPaint.setStrokeWidth(2.0f * host.getResources().getDisplayMetrics().density);
            android.graphics.Path outline = mOutline;
            outline.moveTo(44.50f, 0.40f);
            outline.lineTo(49.50f, 0.04f);
            outline.lineTo(54.50f, 2.15f);
            outline.lineTo(59.87f, 7.50f);
            outline.lineTo(62.04f, 11.50f);
            outline.lineTo(61.69f, 12.50f);
            outline.lineTo(28.11f, 29.50f);
            outline.lineTo(29.50f, 30.11f);
            outline.lineTo(32.50f, 28.27f);
            outline.lineTo(34.50f, 28.42f);
            outline.lineTo(57.50f, 35.99f);
            outline.lineTo(62.64f, 41.50f);
            outline.lineTo(63.66f, 46.50f);
            outline.lineTo(62.65f, 51.50f);
            outline.lineTo(59.76f, 55.50f);
            outline.lineTo(56.50f, 57.85f);
            outline.lineTo(20.50f, 75.81f);
            outline.lineTo(15.50f, 76.93f);
            outline.lineTo(10.50f, 75.80f);
            outline.lineTo(4.95f, 71.50f);
            outline.lineTo(0.96f, 64.50f);
            outline.lineTo(30.52f, 49.50f);
            outline.lineTo(29.50f, 48.40f);
            outline.lineTo(8.50f, 41.70f);
            outline.lineTo(4.84f, 39.50f);
            outline.lineTo(2.04f, 36.50f);
            outline.lineTo(0.03f, 31.50f);
            outline.lineTo(1.36f, 24.50f);
            outline.lineTo(6.50f, 18.99f);
            outline.lineTo(44.50f, 0.40f);
            outline.close();
            host.addOnAttachStateChangeListener(this);
            if (host.isAttachedToWindow()) onViewAttachedToWindow(host);
        }

        void setEnabled(boolean enabled) {
            mEnabled = enabled;
            refresh();
        }

        private boolean canAnimate() {
            return mEnabled && mHost.isAttachedToWindow() && mHost.isShown()
                    && mHost.hasWindowFocus() && isVisible()
                    && android.animation.ValueAnimator.areAnimatorsEnabled();
        }

        private void refresh() {
            unscheduleSelf(this);
            invalidateSelf();
            if (canAnimate()) scheduleSelf(this, android.os.SystemClock.uptimeMillis() + 33);
        }

        @Override
        public void run() { refresh(); }

        @Override
        protected void onBoundsChange(android.graphics.Rect bounds) {
            mMark.setBounds(bounds);
            mMatrix.setRectToRect(new android.graphics.RectF(0, 0, 64, 77),
                    new android.graphics.RectF(bounds), android.graphics.Matrix.ScaleToFit.FILL);
            mOutline.transform(mMatrix, mScaled);
            mMeasure.setPath(mScaled, true);
        }

        @Override
        public void draw(android.graphics.Canvas canvas) {
            mMark.draw(canvas);
            if (!mEnabled) return;
            // ImageView applies its own image matrix; compensate so the final
            // stroke remains 2dp rather than 2 raster pixels.
            mHost.getImageMatrix().getValues(mImageMatrixValues);
            float scale = Math.abs(mImageMatrixValues[android.graphics.Matrix.MSCALE_X]);
            mPaint.setStrokeWidth(2.0f * mHost.getResources().getDisplayMetrics().density
                    / Math.max(0.01f, scale));
            mPaint.setAlpha(mAlpha * 220 / 255);
            float length = mMeasure.getLength();
            float phase = android.animation.ValueAnimator.areAnimatorsEnabled()
                    ? ((android.os.SystemClock.uptimeMillis() - mEpoch) % 3200L) / 3200.0f : 0.0f;
            float start = length * phase;
            float end = start + length * 0.35f;
            mSegment.rewind();
            mMeasure.getSegment(start, Math.min(end, length), mSegment, true);
            if (end > length) mMeasure.getSegment(0, end - length, mSegment, true);
            canvas.drawPath(mSegment, mPaint);
        }

        @Override
        public boolean setVisible(boolean visible, boolean restart) {
            boolean changed = super.setVisible(visible, restart);
            refresh();
            return changed;
        }

        @Override
        public void setAlpha(int alpha) {
            mAlpha = alpha;
            mMark.setAlpha(alpha);
            invalidateSelf();
        }

        @Override
        public void setColorFilter(android.graphics.ColorFilter filter) {
            // Keep the original logo and green accent independent of toolbar tint.
        }

        @Override
        public int getOpacity() { return android.graphics.PixelFormat.TRANSLUCENT; }
        @Override
        public int getIntrinsicWidth() { return mMark.getIntrinsicWidth(); }
        @Override
        public int getIntrinsicHeight() { return mMark.getIntrinsicHeight(); }
        @Override
        public void onWindowFocusChanged(boolean focused) { refresh(); }
        @Override
        public void onGlobalLayout() { refresh(); }
        @Override
        public void onViewAttachedToWindow(View view) {
            if (!mListening) {
                view.getViewTreeObserver().addOnWindowFocusChangeListener(this);
                view.getViewTreeObserver().addOnGlobalLayoutListener(this);
                mListening = true;
            }
            refresh();
        }
        @Override
        public void onViewDetachedFromWindow(View view) {
            unscheduleSelf(this);
            if (view.getViewTreeObserver().isAlive()) {
                view.getViewTreeObserver().removeOnWindowFocusChangeListener(this);
                view.getViewTreeObserver().removeOnGlobalLayoutListener(this);
            }
            mListening = false;
        }
    }

    private static String capitalize(String value) {
        if (value == null || value.isEmpty()) return "Medium";
        return value.substring(0, 1).toUpperCase(java.util.Locale.ROOT) + value.substring(1);
    }
}
