// Copyright 2026 Sandium Authors. BSD-style license.
package org.chromium.chrome.browser.sandium.dark;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import androidx.preference.Preference;
import androidx.preference.PreferenceScreen;
import org.chromium.base.supplier.MonotonicObservableSupplier;
import org.chromium.base.supplier.ObservableSuppliers;
import org.chromium.base.supplier.SettableMonotonicObservableSupplier;
import org.chromium.brave_shields.mojom.FilterListAndroidHandler;
import org.chromium.chrome.browser.settings.BravePreferenceFragment;
import org.chromium.chrome.browser.shields.FilterListServiceFactory;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.ByteBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Local, user-selected files only. Never exports private-profile data or uploads backups. */
public class SandiumRulesPreferences extends BravePreferenceFragment {
    private static final int EXPORT_COLORS = 9401, IMPORT_COLORS = 9402;
    private static final int EXPORT_ADS = 9403, IMPORT_ADS = 9404;
    private final SettableMonotonicObservableSupplier<String> mTitle = ObservableSuppliers.createMonotonic();
    private final ExecutorService mFiles = Executors.newSingleThreadExecutor();
    private final Handler mMain = new Handler(Looper.getMainLooper());
    private FilterListAndroidHandler mAdHandler;
    private AlertDialog mDialog;
    private boolean mBusy, mDestroyed;

    protected boolean colorRulesOnly() { return true; }

    @Override public MonotonicObservableSupplier<String> getPageTitle() { return mTitle; }
    @Override public void onCreatePreferences(Bundle state, String key) {
        super.onCreatePreferences(state, key);
        mTitle.set(colorRulesOnly() ? "Element color corrections" : "Custom blocking rules");
        PreferenceScreen screen = getPreferenceManager().createPreferenceScreen(requireContext());
        setPreferenceScreen(screen);
        if (!usable()) { row(screen, "Unavailable in private browsing", null, null); return; }
        if (colorRulesOnly()) {
            row(screen, "Local color backups", "Backups contain website names and your color corrections. Save them only to a location you trust. Private color corrections are not included.", null);
            row(screen, "View saved color rules", "Website, element, corrected property and color", () -> viewColors());
            row(screen, "Download color rules", "Save a Sandium JSON backup", () -> choose(EXPORT_COLORS));
            row(screen, "Restore color rules", "Merge a backup; existing corrections win conflicts", () -> choose(IMPORT_COLORS));
        } else {
            row(screen, "Local blocking backups", "Backups contain your custom ad and element-blocking filters, not downloaded filter lists. These filters are browser-wide. Save backups only to a location you trust.", null);
            row(screen, "View custom blocking rules", "User-created ad and element-blocking filters", () -> withAds(text -> showText("Custom blocking rules", text.isEmpty() ? "No custom rules saved." : text)));
            row(screen, "Download custom blocking rules", "Save the complete custom filter text in a JSON backup", () -> choose(EXPORT_ADS));
            row(screen, "Restore custom blocking rules", "Append a trusted backup without deleting current filters", () -> choose(IMPORT_ADS));
        }
    }
    private void row(androidx.preference.PreferenceGroup group, String title, String summary, Runnable action) {
        Preference row = new Preference(requireContext()); row.setTitle(title); row.setSummary(summary);
        row.setSelectable(action != null); row.setOnPreferenceClickListener(p -> {
            if (mBusy) { message("A file operation is already in progress."); return true; }
            if (action != null && usable()) action.run(); return true;
        }); group.addPreference(row);
    }
    private boolean usable() {
        return !mDestroyed && getActivity() != null && getProfile() != null
                && getProfile().isNativeInitialized() && !getProfile().shutdownStarted()
                && !getProfile().isOffTheRecord();
    }
    private void message(String text) {
        if (!mDestroyed && getActivity() != null) Toast.makeText(requireContext(), text, Toast.LENGTH_LONG).show();
    }
    private interface TextResult { void accept(String value); }
    private void withAds(TextResult result) {
        if (!usable()) return;
        if (mAdHandler == null) mAdHandler = FilterListServiceFactory.getInstance()
                .getFilterListAndroidHandler(getProfile(), error -> {
                    mBusy = false; mAdHandler = null; message("Custom rule storage is unavailable. Nothing was restored.");
                });
        if (mAdHandler == null) { mBusy = false; message("Custom rule storage is unavailable."); return; }
        mAdHandler.getCustomFilters(text -> { if (usable()) result.accept(text); });
    }
    private void showText(String title, String text) {
        if (!usable()) return;
        TextView view = new TextView(requireContext()); view.setText(text); view.setTextIsSelectable(true);
        int padding = (int) (16 * getResources().getDisplayMetrics().density);
        view.setPadding(padding, padding, padding, padding);
        ScrollView scroll = new ScrollView(requireContext()); scroll.addView(view);
        if (mDialog != null) mDialog.dismiss();
        mDialog = new AlertDialog.Builder(requireContext()).setTitle(title).setView(scroll)
                .setPositiveButton("Done", null).show();
    }
    private void viewColors() {
        try {
            JSONObject sites = new JSONObject(SandiumElementColorsUtils.exportRules(getProfile()));
            ArrayList<String> origins = new ArrayList<>();
            for (Iterator<String> keys = sites.keys(); keys.hasNext();) origins.add(keys.next());
            Collections.sort(origins); StringBuilder text = new StringBuilder();
            for (String origin : origins) {
                text.append(origin).append("\n"); JSONArray rules = sites.getJSONArray(origin);
                for (int i = 0; i < rules.length(); i++) {
                    JSONObject rule = rules.getJSONObject(i); int property = rule.getInt("property");
                    text.append("• ").append(rule.getString("tag"));
                    if (!rule.getString("id").isEmpty()) text.append(" #").append(rule.getString("id"));
                    else text.append(" (saved structural match)");
                    text.append(" · ").append(property == 0 ? "Text" : property == 1 ? "Background" : "Image artwork")
                            .append(" · ").append(String.format(java.util.Locale.ROOT, "#%06X", rule.getInt("rgb"))).append("\n");
                    if (rule.has("locator")) text.append("  Match: ").append(rule.getJSONObject("locator").toString()).append("\n");
                }
                text.append("\n");
            }
            showText("Saved color rules", text.length() == 0 ? "No color corrections saved." : text.toString());
        } catch (Exception error) { message("Could not read saved color rules."); }
    }
    private boolean ownsRequest(int request) {
        return colorRulesOnly() ? request == EXPORT_COLORS || request == IMPORT_COLORS
                : request == EXPORT_ADS || request == IMPORT_ADS;
    }
    private void choose(int request) {
        if (!ownsRequest(request)) return;
        boolean export = request == EXPORT_COLORS || request == EXPORT_ADS;
        Intent intent = new Intent(export ? Intent.ACTION_CREATE_DOCUMENT : Intent.ACTION_OPEN_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE).setType(export ? "application/json" : "*/*");
        if (export) intent.putExtra(Intent.EXTRA_TITLE, request == EXPORT_COLORS
                ? "Sandium-color-rules.json" : "Sandium-custom-ad-rules.json");
        try { mBusy = true; startActivityForResult(intent, request); }
        catch (android.content.ActivityNotFoundException unavailable) { mBusy = false; message("No file picker is available."); }
    }
    @Override public void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (!ownsRequest(request)) return;
        mBusy = false;
        if (result != Activity.RESULT_OK || data == null || data.getData() == null || !usable()) return;
        Uri uri = data.getData();
        if (!"content".equals(uri.getScheme())) { message("Choose a file through the document picker."); return; }
        boolean colors = request == EXPORT_COLORS || request == IMPORT_COLORS;
        String kind = colors ? SandiumRuleBackup.COLORS : SandiumRuleBackup.ADS;
        mBusy = true;
        if (request == EXPORT_COLORS) write(uri, kind, SandiumElementColorsUtils.exportRules(getProfile()));
        else if (request == EXPORT_ADS) withAds(text -> write(uri, kind, text));
        else read(uri, kind);
    }
    private void write(Uri uri, String kind, String payload) {
        final String backup;
        try { backup = SandiumRuleBackup.encode(kind, payload); }
        catch (Exception error) { mBusy = false; message("Could not create backup. No rules changed."); return; }
        android.content.ContentResolver resolver = requireContext().getContentResolver();
        mFiles.execute(() -> {
            boolean success = false;
            try (OutputStream stream = resolver.openOutputStream(uri, "wt")) {
                if (stream == null) throw new java.io.IOException("No output stream");
                stream.write(backup.getBytes(StandardCharsets.UTF_8)); stream.flush(); success = true;
            } catch (Exception error) { /* Report after returning to the UI thread. */ }
            final boolean saved = success;
            mMain.post(() -> { mBusy = false; message(saved ? "Backup saved." : "Could not save backup. The destination file may be incomplete; retry export."); });
        });
    }
    private void read(Uri uri, String kind) {
        android.content.ContentResolver resolver = requireContext().getContentResolver();
        mFiles.execute(() -> {
            String payload = null;
            try (InputStream stream = resolver.openInputStream(uri)) {
                if (stream == null) throw new java.io.IOException("No input stream");
                ByteArrayOutputStream bytes = new ByteArrayOutputStream(); byte[] buffer = new byte[8192];
                int count; while ((count = stream.read(buffer)) != -1) {
                    if (bytes.size() + count > SandiumRuleBackup.MAX_BYTES) throw new java.io.IOException("Too large");
                    bytes.write(buffer, 0, count);
                }
                String text = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                        .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes.toByteArray())).toString();
                payload = SandiumRuleBackup.decode(kind, text);
            } catch (Exception error) { /* Reject the entire file, never partially restore. */ }
            final String imported = payload;
            mMain.post(() -> {
                mBusy = false; if (!usable()) return;
                if (imported == null) { message("Invalid, oversized or wrong-category backup. Nothing was restored."); return; }
                if (SandiumRuleBackup.COLORS.equals(kind)) previewColors(imported); else previewAds(imported);
            });
        });
    }
    private void previewColors(String imported) {
        try {
            JSONObject result = new JSONObject(SandiumElementColorsUtils.importRules(getProfile(), imported, false));
            if (!result.getBoolean("ok")) { message("Backup rejected. " + result.optString("error")); return; }
            confirm("Restore color rules?", result.optInt("added") + " new corrections; "
                    + result.optInt("conflicts") + " conflicts kept unchanged; " + result.optInt("duplicates") + " already saved. Existing rules will not be deleted. Reload pages to apply restored colors.", () -> {
                try {
                    JSONObject applied = new JSONObject(SandiumElementColorsUtils.importRules(getProfile(), imported, true));
                    message(applied.getBoolean("ok") ? "Color rules restored. Reload pages to apply." : "Nothing restored. " + applied.optString("error"));
                } catch (Exception error) { message("Could not restore color rules."); }
            });
        } catch (Exception error) { message("Invalid color rules. Nothing restored."); }
    }
    private void previewAds(String imported) {
        withAds(existing -> {
            try {
                String merged = SandiumRuleBackup.mergeAds(existing, imported);
                if (merged.equals(existing)) { message("This backup adds no custom filter text."); return; }
                confirm("Restore custom ad rules?", "Append " + imported.length()
                        + " characters without deleting current rules. Only restore backups you trust: filters can change which content loads. Custom ad rules are browser-wide. Downloaded filter lists are not included.", () -> {
                    // Native UI-sequence read+append+write is one operation. An async
                    // GetCustomFilters -> UpdateCustomFilters pair could lose another window's edits.
                    boolean ok = SandiumElementColorsUtils.appendAdRules(getProfile(), imported);
                    message(ok ? "Custom ad rules restored." : "Custom ad rule restore failed. Nothing was removed.");
                });
            } catch (Exception error) { message("Rule limit exceeded. Nothing restored."); }
        });
    }
    private void confirm(String title, String text, Runnable action) {
        if (!usable()) return;
        if (mDialog != null) mDialog.dismiss();
        mDialog = new AlertDialog.Builder(requireContext()).setTitle(title).setMessage(text)
                .setNegativeButton("Cancel", null).setPositiveButton("Restore", (dialog, which) -> {
                    if (usable()) action.run();
                }).show();
    }
    @Override public void onDestroy() {
        mDestroyed = true;
        if (mDialog != null) mDialog.dismiss();
        if (mAdHandler != null) mAdHandler.close();
        mFiles.shutdown();
        super.onDestroy();
    }
}
