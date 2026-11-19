package org.chromium.chrome.browser.privacy.secure_dns;

import android.content.Context;
import android.net.Uri;
import org.chromium.base.ContextUtils;
import org.chromium.base.ThreadUtils;
import org.chromium.base.library_loader.LibraryLoader;
import org.chromium.chrome.browser.net.SecureDnsManagementMode;
import org.chromium.chrome.browser.settings.SettingsNavigationFactory;
import org.chromium.net.SecureDnsMode;
import org.json.JSONArray;
import org.json.JSONObject;
import org.json.JSONException;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/** One UI facade over Chromium's browser-global Secure DNS preferences. */
public final class SandiumSecureDns {
    private static final String CUSTOM = "sandium_secure_dns_custom_providers_v1";
    private SandiumSecureDns() {}
    public static final class Provider {
        public final String id, name, template;
        public Provider(String id, String name, String template) {
            this.id=id; this.name=name; this.template=template;
        }
    }
    public static final class State {
        public final boolean enabled;
        public final String providerId, providerName;
        State(boolean enabled, String id, String name) {
            this.enabled=enabled; providerId=id; providerName=name;
        }
    }
    public static boolean isReady() { return LibraryLoader.getInstance().isInitialized(); }
    public static boolean isManaged() {
        ThreadUtils.assertOnUiThread();
        return !isReady() || SecureDnsBridge.isModeManaged() || SecureDnsBridge.isConfigManaged()
                || SecureDnsBridge.getManagementMode() != SecureDnsManagementMode.NO_OVERRIDE;
    }
    public static List<Provider> getProviders() {
        ThreadUtils.assertOnUiThread();
        List<Provider> list=new ArrayList<>();
        list.add(new Provider("cloudflare", "Cloudflare (1.1.1.1)", "https://cloudflare-dns.com/dns-query"));
        list.add(new Provider("google", "Google Public DNS", "https://dns.google/dns-query"));
        list.add(new Provider("quad9", "Quad9", "https://dns.quad9.net/dns-query"));
        try {
            JSONArray entries=new JSONArray(ContextUtils.getAppSharedPreferences().getString(CUSTOM,"[]"));
            for(int i=0;i<entries.length();i++) {
                JSONObject entry=entries.getJSONObject(i);
                list.add(new Provider(entry.getString("id"),entry.getString("name"),entry.getString("template")));
            }
        } catch (JSONException ignored) { /* Invalid metadata never alters native DNS. */ }
        if(isReady()) {
            String config=SecureDnsBridge.getConfig(); boolean found=config.isEmpty();
            for(Provider provider:list) if(provider.template.equals(config)) found=true;
            if(!found) list.add(new Provider("custom:current","Current custom provider",config));
            if(SecureDnsBridge.getMode()==SecureDnsMode.AUTOMATIC)
                list.add(new Provider("automatic","Automatic",""));
        }
        return list;
    }
    public static State getState() {
        ThreadUtils.assertOnUiThread();
        if(!isReady()) return new State(false,"","Off");
        int mode=SecureDnsBridge.getMode();
        if(mode==SecureDnsMode.OFF) return new State(false,"","Off");
        if(mode==SecureDnsMode.AUTOMATIC) return new State(true,"automatic","Automatic");
        String config=SecureDnsBridge.getConfig();
        for(Provider provider:getProviders()) if(provider.template.equals(config))
            return new State(true,provider.id,provider.name);
        return new State(true,"custom:current","Current custom provider");
    }
    public static boolean setEnabled(boolean enabled) {
        if(isManaged()) return false;
        if(!enabled) { SecureDnsBridge.setMode(SecureDnsMode.OFF); return true; }
        String config=SecureDnsBridge.getConfig();
        if(!config.isEmpty() && SecureDnsBridge.validateConfig(config)) {
            SecureDnsBridge.setMode(SecureDnsMode.SECURE); return true;
        }
        return false; // Enabling without a prior endpoint requires an explicit provider choice.
    }
    public static boolean selectProvider(String id) {
        if(isManaged()) return false;
        if("automatic".equals(id)) { SecureDnsBridge.setMode(SecureDnsMode.AUTOMATIC); return true; }
        for(Provider provider:getProviders()) if(provider.id.equals(id)) {
            if(!SecureDnsBridge.setConfig(provider.template)) return false;
            SecureDnsBridge.setMode(SecureDnsMode.SECURE); return true;
        }
        return false;
    }
    public static boolean validCustom(String template) {
        ThreadUtils.assertOnUiThread();
        if(!isReady() || template.isEmpty()) return false;
        for(int i=0;i<template.length();i++)
            if(Character.isWhitespace(template.charAt(i)) || Character.isISOControl(template.charAt(i))) return false;
        Uri uri=Uri.parse(template.replace("{?dns}",""));
        return "https".equalsIgnoreCase(uri.getScheme()) && uri.getHost()!=null
                && uri.getUserInfo()==null && uri.getFragment()==null
                && SecureDnsBridge.validateConfig(template);
    }
    /** Save metadata only. Saving does not change the active resolver. */
    public static boolean saveCustom(String name,String template) {
        if(isManaged() || name.trim().isEmpty() || name.length()>80 || !validCustom(template)) return false;
        JSONArray entries=new JSONArray();
        for(Provider provider:getProviders()) if(provider.template.equals(template)) return false;
        try {
            for(Provider provider:getProviders()) {
                if(!provider.id.startsWith("custom:") || "custom:current".equals(provider.id)) continue;
                if(provider.template.equals(template)) return false;
                entries.put(new JSONObject().put("id",provider.id).put("name",provider.name).put("template",provider.template));
            }
            entries.put(new JSONObject().put("id","custom:"+UUID.randomUUID()).put("name",name.trim()).put("template",template));
        } catch(JSONException e) { return false; }
        ContextUtils.getAppSharedPreferences().edit().putString(CUSTOM,entries.toString()).apply();
        return true;
    }
    public static boolean removeCustom(String id) {
        if(isManaged()) return false;
        JSONArray entries=new JSONArray(); boolean removed=false;
        try {
            for(Provider provider:getProviders()) {
                if(!provider.id.startsWith("custom:") || "custom:current".equals(provider.id)) continue;
                if(provider.id.equals(id)) { removed=true; continue; }
                entries.put(new JSONObject().put("id",provider.id).put("name",provider.name).put("template",provider.template));
            }
        } catch(JSONException e) { return false; }
        if(removed) ContextUtils.getAppSharedPreferences().edit().putString(CUSTOM,entries.toString()).apply();
        // Native active endpoint remains intact and appears as Current custom provider.
        return removed;
    }
    /** Invoke only on an auxiliary thread after explicit Test; no setting mutation. */
    static boolean probe(String template) { return SecureDnsBridge.probeConfig(template); }
    public static void openSettings(Context context) {
        SettingsNavigationFactory.createSettingsNavigation().startSettings(context,SecureDnsSettings.class);
    }
}
