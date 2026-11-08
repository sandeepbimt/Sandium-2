#!/usr/bin/env python3
"""Offline, idempotent tests for Sandium's native filter subscriptions."""
from __future__ import annotations

import ast
import re
import runpy
import tempfile
from pathlib import Path

PATCH = runpy.run_path(str(Path(__file__).with_name("apply-sandium-filter-subscriptions.py")))
FILTERS = PATCH["FILTERS"]
apply_android_sources = PATCH["apply_android_sources"]
verify_android_sources = PATCH["verify_android_sources"]

FRAGMENT_FIXTURE = """import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import org.chromium.mojo_base.mojom.Value;
import java.util.ArrayList;
import java.util.Arrays;

public class ContentFilteringFragment extends BravePreferenceFragment
        implements FragmentSettingsNavigation,
                BraveContentFilteringListener,
                BottomInsetViewProvider {
    private RecyclerView mRecyclerView;

    private void setData() {
        initFilterListAndroidHandler();
        mRecyclerView = (RecyclerView) getView().findViewById(R.id.recyclerview);
        LinearLayoutManager linearLayoutManager =
                new LinearLayoutManager(getActivity(), LinearLayoutManager.VERTICAL, false);
        mRecyclerView.setLayoutManager(linearLayoutManager);
        mAdapter = new ContentFilteringAdapter(getActivity(), this);
        mRecyclerView.setAdapter(mAdapter);
        getSubscriptionFilters();
        getFilterLists();
    }

    private void getSubscriptionFilters() {
        if (mFilterListAndroidHandler != null) {
            mFilterListAndroidHandler.getSubscriptions(
                    subscriptions -> {
                        mSubscriptionFilterLists = new ArrayList<>(Arrays.asList(subscriptions));
                        mAdapter.setSubscriptionFilterLists(mSubscriptionFilterLists);
                    });
        }
    }

    private void getFilterLists() {
        if (mFilterListAndroidHandler != null) {
            mFilterListAndroidHandler.getFilterLists(filterLists -> {
                mFilterLists = filterLists.storage;
                mAdapter.setFilterLists(mFilterLists);
            });
        }
    }

    public void onCreateOptionsMenu(Menu menu, MenuInflater inflater) {
        inflater.inflate(R.menu.menu_custom_filter_list, menu);
        mUpdateFilterListItem = menu.findItem(R.id.update_filter_list_id);
    }

    public boolean onOptionsItemSelected(MenuItem item) {
        int id = item.getItemId();
        if (id == R.id.menu_id_edit) {
            isEditSelected(true);
            return true;
        } else if (id == R.id.menu_id_done) {
            isEditSelected(false);
            return true;
        } else if (item.getItemId() == R.id.update_filter_list_id) {
            if (mFilterListAndroidHandler != null) {
                mFilterListAndroidHandler.updateFilterLists(
                        isSuccess -> {
                            if (isSuccess) {
                                setData();
                            }
                            String message =
                                    isSuccess
                                            ? getString(R.string.update_filter_list_success_text)
                                            : getString(R.string.update_filter_list_fail_text);
                            Toast.makeText(getActivity(), message, Toast.LENGTH_SHORT).show();
                        });
            }
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    private void isEditSelected(boolean isEditable) {
        mUpdateFilterListItem.setVisible(!isEditable);
    }
}
"""

ADAPTER_FIXTURE = """import java.util.ArrayList;
public class ContentFilteringAdapter extends RecyclerView.Adapter<RecyclerView.ViewHolder> {
    private ArrayList<SubscriptionInfo> mSubscriptionFilterLists;
    private Value mFilterLists[];
    private final Context mContext;
    private final BraveContentFilteringListener mBraveContentFileringListener;

    public ContentFilteringAdapter(
            Context context, BraveContentFilteringListener braveContentFileringListener) {
        mContext = context;
        mBraveContentFileringListener = braveContentFileringListener;
    }

    public void bindSubscription(SubscriptionInfo customFilter) {
                String url = customFilter.subscriptionUrl.url;
                if (customFilter.title != null && customFilter.title.length() > 0) {
            customFilterListViewHolder.mTitleText.setText(customFilter.title);
            customFilterListViewHolder.mTitleText.setVisibility(View.VISIBLE);

        } else {
            Uri uri = Uri.parse(url);
            customFilterListViewHolder.mTitleText.setText(uri.getHost());
        }
    }

    public int getItemCount() {
        int count = mSubscriptionFilterLists.size() + FOUR_ITEMS_SPACE;
        if (mFilterLists != null) {
            count += mFilterLists.length;
        }
        return count;
    }

    public int getItemViewType(int position) {
        if (position == 0 || position == mSubscriptionFilterLists.size() + THREE_ITEMS_SPACE) {
            return TYPE_FILTER_HEADER;
        } else if (position > 0 && position <= mSubscriptionFilterLists.size() + TWO_ITEMS_SPACE) {
            return TYPE_CUSTOM_FILTER_LIST;
        } else {
            return TYPE_FILTER_LIST;
        }
    }

    public void setFilterLists(Value filterLists[]) {
        mFilterLists = filterLists;
        // mSubscriptionFilterLists could be null if setSubscriptionFilterLists
        // hasn't been called yet. notifyItemRangeInserted is called inside
        // setSubscriptionFilterLists, so we are good to skip it in that place
        if (mSubscriptionFilterLists != null) {
            notifyItemRangeInserted(
                    mSubscriptionFilterLists.size() + THREE_ITEMS_SPACE,
                    mFilterLists.length + ONE_ITEM_SPACE);
        }
    }
}
"""

def main() -> None:
    # Catch patcher call/signature drift before applying any source changes.
    for patcher_name in (
        "apply-sandium-filter-subscriptions.py",
        "apply-sandium-filter-bootstrap.py",
    ):
        patcher_path = Path(__file__).with_name(patcher_name)
        patcher_ast = ast.parse(patcher_path.read_text(encoding="utf-8"))
        for node in ast.walk(patcher_ast):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "replace_once":
                assert len(node.args) == 5 and not node.keywords, (
                    f"{patcher_name}:{node.lineno}: replace_once expects exactly "
                    f"5 positional arguments, got {len(node.args)}"
                )

    assert len(FILTERS) == 30
    assert len({url for url, _ in FILTERS}) == 30
    with tempfile.TemporaryDirectory(prefix="sandium-filter-subscriptions-test-") as directory:
        core = Path(directory)
        fragment = core / "android/java/org/chromium/chrome/browser/shields/ContentFilteringFragment.java"
        adapter = core / "android/java/org/chromium/chrome/browser/shields/ContentFilteringAdapter.java"
        fragment.parent.mkdir(parents=True, exist_ok=True)
        fragment.write_text(FRAGMENT_FIXTURE, encoding="utf-8")
        adapter.write_text(ADAPTER_FIXTURE, encoding="utf-8")

        apply_android_sources(core)
        verify_android_sources(core)
        apply_android_sources(core)
        verify_android_sources(core)

        fragment_text = fragment.read_text(encoding="utf-8")
        adapter_text = adapter.read_text(encoding="utf-8")
        assert "getSubscriptions(subscriptions ->" in fragment_text
        assert 'Log.i("SandiumFilterLists"' in fragment_text
        assert "Log.i(TAG" not in fragment_text
        assert "createSubscription(subscriptionUrl)" in fragment_text
        assert re.search(r"putStringSet\s*\(\s*SEEDED_URLS_PREF", fragment_text), \
            "seeded URL preferences are not persisted"
        assert "existingUrls.contains(url)" in fragment_text
        assert "seededUrls.add(url)" in fragment_text
        assert "getFilterLists(filterLists" not in fragment_text
        assert "updateFilterLists(" not in fragment_text
        assert "SANDIUM_FILTER_REFRESH_PLACEHOLDER" in fragment_text
        assert "        ensureSandiumDefaultSubscriptions();\n" not in fragment_text
        assert "SANDIUM_NATIVE_STARTUP_SEEDING_ONLY" in fragment_text
        assert "getSandiumFilterDisplayName(url)" in adapter_text
        assert "mFilterLists.length > 0" in adapter_text
        assert "mSubscriptionFilterLists = new ArrayList<>()" in adapter_text
        assert "defaultEnabled=true" in fragment_text
        assert "DEFAULT_DISABLED_FILTER_URLS" not in fragment_text
        assert "SANDIUM_FILTER_REFRESH_PLACEHOLDER" in fragment_text
        expected_titles = {
            "uBlock filters – Ads",
            "AdGuard – Ads",
            "EasyPrivacy",
            "Online Malicious URL Blocklist",
            "Dan Pollock’s hosts file",
            "EasyList – Cookie Notices",
            "AdGuard – Cookie Notices",
            "uBlock filters – Cookie Notices",
            "EasyList – Social Widgets",
            "AdGuard – Social Widgets",
            "Fanboy – Anti-Facebook",
            "EasyList – AI Widgets",
            "EasyList – Chat Widgets",
            "EasyList – Newsletter Notices",
            "EasyList – Notifications",
            "EasyList – Other Annoyances",
            "AdGuard – Mobile App Banners",
            "AdGuard – Other Annoyances",
            "AdGuard – Popup Overlays",
            "AdGuard – Widgets",
            "uBlock filters – Annoyances",
            "🇮🇳in 🇱🇰lk 🇳🇵np: IndianList",
        }
        for title in expected_titles:
            assert title in fragment_text, f"missing visible filter title: {title}"
        print("SANDIUM_FILTER_SUBSCRIPTIONS_UNIT_TEST=PASS lists=30 unique=true default_enabled=true idempotent=true")
if __name__ == "__main__":
    main()
