// Copyright 2026 Sandium Authors. BSD-style license.
package org.chromium.chrome.browser.sandium.dark;

import org.json.JSONException;
import org.json.JSONObject;
import org.json.JSONTokener;
import java.nio.charset.StandardCharsets;

/** Versioned local backups. These files contain site names and user-created rules. */
public final class SandiumRuleBackup {
    public static final int MAX_BYTES = 8 * 1024 * 1024;
    public static final String COLORS = "element-colors";
    public static final String ADS = "custom-ad-rules";
    private SandiumRuleBackup() {}

    public static String encode(String kind, String payload) throws JSONException {
        JSONObject root = new JSONObject();
        root.put("format", "sandium-rules"); root.put("version", 1); root.put("kind", kind);
        if (COLORS.equals(kind)) root.put("rules", new JSONObject(payload));
        else if (ADS.equals(kind)) root.put("rules", payload);
        else throw new JSONException("Unknown backup category");
        String result = root.toString(2);
        bounded(result);
        return result;
    }
    public static String decode(String kind, String input) throws JSONException {
        bounded(input);
        JSONTokener reader = new JSONTokener(input);
        Object value = reader.nextValue();
        if (!(value instanceof JSONObject) || reader.nextClean() != 0)
            throw new JSONException("Invalid backup document");
        JSONObject root = (JSONObject) value;
        if (root.length() != 4 || !"sandium-rules".equals(root.optString("format"))
                || !(root.get("version") instanceof Integer) || root.getInt("version") != 1
                || !kind.equals(root.optString("kind")))
            throw new JSONException("Wrong backup category or unsupported version");
        Object rules = root.get("rules");
        if (COLORS.equals(kind) && rules instanceof JSONObject) return rules.toString();
        if (ADS.equals(kind) && rules instanceof String) {
            if (((String) rules).indexOf('\0') >= 0) throw new JSONException("Invalid filter text");
            return (String) rules;
        }
        throw new JSONException("Invalid backup payload");
    }
    public static void bounded(String input) throws JSONException {
        if (input.getBytes(StandardCharsets.UTF_8).length > MAX_BYTES)
            throw new JSONException("Backup exceeds 8 MiB");
    }
    /** Keep both texts intact. Never split/deduplicate/reorder conditional filter blocks. */
    public static String mergeAds(String existing, String incoming) throws JSONException {
        if (incoming.isEmpty() || existing.equals(incoming) || existing.endsWith("\n" + incoming)) return existing;
        String merged = existing.isEmpty() ? incoming
                : existing + (existing.endsWith("\n") ? "" : "\n") + incoming;
        bounded(merged);
        return merged;
    }
}
