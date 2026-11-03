#!/usr/bin/env python3
"""Offline transformation tests for Sandium's Brave/uBO filter integration."""
from __future__ import annotations

import tempfile
from pathlib import Path
import runpy

# The production patch filename intentionally uses hyphens, so it cannot be
# imported with a normal "from module import ..." statement.
_PATCH = runpy.run_path(
    str(Path(__file__).with_name("apply-sandium-adblock.py"))
)
FRESH_INSTALL_FILTER_UUIDS = _PATCH["FRESH_INSTALL_FILTER_UUIDS"]
apply_patches = _PATCH["apply_patches"]
verify_patches = _PATCH["verify_patches"]

MANAGER_FIXTURE = """  // If there are currently no components to update, then run the callback with
  // a success value in a future turn.
  if (component_filters_providers_.empty()) {
    std::move(callback).Run(true);
    return;
  }

  std::vector<std::string> component_ids = {
"""

FRAGMENT_FIXTURE = """import android.content.Context;
import android.content.Intent;
import android.os.Bundle;

import java.util.ArrayList;
import java.util.Arrays;

public class ContentFilteringFragment extends BravePreferenceFragment
        implements FragmentSettingsNavigation,
                BraveContentFilteringListener,
                BottomInsetViewProvider {
    private RecyclerView mRecyclerView;

    private void getFilterLists() {
        if (mFilterListAndroidHandler != null) {
            mFilterListAndroidHandler.getFilterLists(filterLists -> {
                mFilterLists = filterLists.storage;
                mAdapter.setFilterLists(mFilterLists);
            });
        }
    }

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

    @Override
    public void onDestroy() {
        if (mFilterListAndroidHandler != null) {
"""

ADAPTER_FIXTURE = """    public void setFilterLists(Value filterLists[]) {
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
"""


def main() -> None:
    assert len(FRESH_INSTALL_FILTER_UUIDS) == 6
    assert len(FRESH_INSTALL_FILTER_UUIDS) == len(set(FRESH_INSTALL_FILTER_UUIDS))

    with tempfile.TemporaryDirectory(prefix="sandium-adblock-test-") as tmp:
        core = Path(tmp)
        manager = core / (
            "components/brave_shields/core/browser/"
            "ad_block_component_service_manager.cc"
        )
        fragment = core / (
            "android/java/org/chromium/chrome/browser/shields/"
            "ContentFilteringFragment.java"
        )
        adapter = core / (
            "android/java/org/chromium/chrome/browser/shields/"
            "ContentFilteringAdapter.java"
        )
        for path in (manager, fragment, adapter):
            path.parent.mkdir(parents=True, exist_ok=True)
        manager.write_text(MANAGER_FIXTURE, encoding="utf-8")
        fragment.write_text(FRAGMENT_FIXTURE, encoding="utf-8")
        adapter.write_text(ADAPTER_FIXTURE, encoding="utf-8")

        apply_patches(core)
        verify_patches(core)

        # All transforms must be idempotent on a second application.
        apply_patches(core)
        verify_patches(core)

        fragment_text = fragment.read_text(encoding="utf-8")
        adapter_text = adapter.read_text(encoding="utf-8")
        assert "requestFilterListCatalogueRefresh" in fragment_text
        assert "MAX_FILTER_LIST_UPDATE_ATTEMPTS = 3" in fragment_text
        assert "notifyDataSetChanged();" in adapter_text
        for uuid in FRESH_INSTALL_FILTER_UUIDS:
            assert uuid in fragment_text, f"missing selected catalogue UUID: {uuid}"

    print("SANDIUM_ADBLOCK_UNIT_TEST=PASS transformation=idempotent catalogue=curated")


if __name__ == "__main__":
    main()
