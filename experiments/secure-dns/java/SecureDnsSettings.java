// Copyright 2020 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package org.chromium.chrome.browser.privacy.secure_dns;

import android.app.AlertDialog;
import android.content.Context;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.preference.Preference;
import androidx.preference.PreferenceScreen;
import org.chromium.base.supplier.MonotonicObservableSupplier;
import org.chromium.base.supplier.ObservableSuppliers;
import org.chromium.base.supplier.SettableMonotonicObservableSupplier;
import org.chromium.build.annotations.Nullable;
import org.chromium.chrome.browser.settings.ChromeBaseSettingsFragment;
import org.chromium.chrome.browser.settings.search.ChromeBaseSearchIndexProvider;
import java.util.List;

/** Browser-global Secure DNS settings. Android Private DNS is never modified. */
public class SecureDnsSettings extends ChromeBaseSettingsFragment {
    private final SettableMonotonicObservableSupplier<String> mPageTitle=ObservableSuppliers.createMonotonic();
    public static String getSummary(Context context) {
        return SandiumSecureDns.getState().providerName;
    }
    @Override public void onCreatePreferences(@Nullable Bundle state,@Nullable String key) {
        mPageTitle.set(getString(R.string.settings_secure_dns_title));
        rebuild();
    }
    @Override public void onResume() { super.onResume(); rebuild(); }
    private void rebuild() {
        Context context=requireContext();
        PreferenceScreen screen=getPreferenceManager().createPreferenceScreen(context);
        setPreferenceScreen(screen);
        boolean managed=SandiumSecureDns.isManaged();
        SandiumSecureDns.State state=SandiumSecureDns.getState();
        Preference choose=new Preference(context);choose.setTitle(R.string.sandium_dns_provider);
        choose.setSummary(managed ? getString(R.string.sandium_dns_managed) : state.providerName);choose.setEnabled(!managed);
        choose.setOnPreferenceClickListener(p->{showProviders();return true;});screen.addPreference(choose);
        Preference add=new Preference(context);add.setTitle(R.string.sandium_dns_add);add.setEnabled(!managed);
        add.setOnPreferenceClickListener(p->{showAdd();return true;});screen.addPreference(add);
        for(SandiumSecureDns.Provider provider:SandiumSecureDns.getProviders()) {
            if(!provider.id.startsWith("custom:") || "custom:current".equals(provider.id)) continue;
            Preference item=new Preference(context);item.setTitle(provider.name);
            item.setSummary(provider.template);item.setEnabled(!managed);
            item.setOnPreferenceClickListener(p->{new AlertDialog.Builder(context)
                    .setTitle(provider.name).setMessage(R.string.sandium_dns_remove_note)
                    .setPositiveButton(R.string.sandium_dns_remove,(d,w)->{SandiumSecureDns.removeCustom(provider.id);rebuild();})
                    .setNegativeButton(android.R.string.cancel,null).show();return true;});screen.addPreference(item);
        }
        Preference note=new Preference(context);note.setSelectable(false);
        note.setSummary(R.string.sandium_dns_explanation);screen.addPreference(note);
    }
    private void showProviders() {
        List<SandiumSecureDns.Provider> providers=SandiumSecureDns.getProviders();
        CharSequence[] names=new CharSequence[providers.size()+1];names[0]=getString(R.string.text_off);
        int selected=0;SandiumSecureDns.State state=SandiumSecureDns.getState();
        for(int i=0;i<providers.size();i++) {names[i+1]=providers.get(i).name;if(state.providerId.equals(providers.get(i).id))selected=i+1;}
        new AlertDialog.Builder(requireContext()).setTitle(R.string.sandium_dns_provider)
                .setSingleChoiceItems(names,selected,(dialog,index)->{
                    if(index==0)SandiumSecureDns.setEnabled(false);else SandiumSecureDns.selectProvider(providers.get(index-1).id);
                    dialog.dismiss();rebuild();}).setNegativeButton(android.R.string.cancel,null).show();
    }
    private void showAdd() {
        Context context=requireContext();LinearLayout layout=new LinearLayout(context);layout.setOrientation(LinearLayout.VERTICAL);
        int pad=(int)(20*context.getResources().getDisplayMetrics().density);layout.setPadding(pad,pad,pad,pad);
        EditText name=new EditText(context);name.setSingleLine();name.setHint(R.string.sandium_dns_name);
        EditText endpoint=new EditText(context);endpoint.setSingleLine();endpoint.setHint(R.string.sandium_dns_endpoint);
        endpoint.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_URI);
        TextView result=new TextView(context);result.setText(R.string.sandium_dns_test_note);
        layout.addView(name);layout.addView(endpoint);layout.addView(result);
        AlertDialog dialog=new AlertDialog.Builder(context).setTitle(R.string.sandium_dns_add).setView(layout)
                .setPositiveButton(R.string.sandium_dns_save,null).setNeutralButton(R.string.sandium_dns_test,null)
                .setNegativeButton(android.R.string.cancel,null).create();
        final int[] generation={0};dialog.setOnDismissListener(d->generation[0]++);
        dialog.setOnShowListener(d->{
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
                if(SandiumSecureDns.saveCustom(name.getText().toString(),endpoint.getText().toString().trim())) {dialog.dismiss();rebuild();}
                else result.setText(R.string.sandium_dns_invalid);
            });
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v->{
                String template=endpoint.getText().toString().trim();
                if(SandiumSecureDns.isManaged() || !SandiumSecureDns.validCustom(template)) {result.setText(R.string.sandium_dns_invalid);return;}
                final int token=++generation[0];result.setText(R.string.sandium_dns_testing);
                dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setEnabled(false);
                endpoint.setEnabled(false);
                Handler main=new Handler(Looper.getMainLooper());
                new Thread(()->{
                    boolean success;
                    try { success=SandiumSecureDns.probe(template); } catch(RuntimeException error) { success=false; }
                    final boolean reachable=success;
                    main.post(()->{
                        if(!isAdded() || !dialog.isShowing() || generation[0]!=token)return;
                        dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setEnabled(true);
                        endpoint.setEnabled(true);
                        result.setText(reachable ? R.string.sandium_dns_test_ok : R.string.sandium_dns_test_fail);
                    });
                },"Sandium-DNS-test").start();
            });
        });dialog.show();
    }
    @Override public MonotonicObservableSupplier<String> getPageTitle(){return mPageTitle;}
    @Override public @AnimationType int getAnimationType(){return AnimationType.PROPERTY;}
    public static final ChromeBaseSearchIndexProvider SEARCH_INDEX_DATA_PROVIDER =
            new ChromeBaseSearchIndexProvider(SecureDnsSettings.class.getName(),R.xml.secure_dns_settings);
}
