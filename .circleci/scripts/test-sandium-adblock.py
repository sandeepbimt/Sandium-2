#!/usr/bin/env python3
"""Offline source-anchor and idempotence tests for the Brave v1.99.54 patch."""
from __future__ import annotations

import runpy
import tempfile
from pathlib import Path

PATCH = runpy.run_path(str(Path(__file__).with_name("apply-sandium-adblock.py")))
apply_patches = PATCH["apply_patches"]
verify_patches = PATCH["verify_patches"]
PIN = PATCH["PIN"]

MANAGER = """#include "base/location.h"

void AdBlockComponentServiceManager::UpdateFilterLists(
    base::OnceCallback<void(bool)> callback) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);

  // If there are currently no components to update, then run the callback with
  // a success value in a future turn.
  if (component_filters_providers_.empty()) {
    std::move(callback).Run(true);
    return;
  }

  std::vector<std::string> component_ids = {
      crx_file::id_util::GenerateIdFromHash(
          kAdBlockResourceComponentPublicKeySHA256),
      crx_file::id_util::GenerateIdFromHash(
          kAdBlockFilterListCatalogComponentPublicKeySHA256),
  };

  for (const auto& [key, provider] : component_filters_providers_) {
    component_ids.push_back(provider->component_id());
  }

  auto on_updated = [](decltype(callback) cb, update_client::Error error) {
    std::move(cb).Run(error == update_client::Error::NONE ||
                      error == update_client::Error::UPDATE_IN_PROGRESS);
  };

  brave_component_updater::BraveOnDemandUpdater::GetInstance()->OnDemandUpdate(
      component_ids, component_updater::OnDemandUpdater::Priority::FOREGROUND,
      base::BindOnce(on_updated, std::move(callback)));
}
"""

MAIN_DELEGATE = """#include "base/lazy_instance.h"
#include "brave/components/brave_component_updater/browser/switches.h"
#include "build/build_config.h"

void BraveMainDelegate::AppendCommandLineOptions() {
  auto* command_line = base::CommandLine::ForCurrentProcess();
  command_line->AppendSwitch(switches::kDisableDomainReliability);
}
"""

FRAGMENT = """import android.content.Context;
import android.content.Intent;
import android.os.Bundle;

public class ContentFilteringFragment extends BravePreferenceFragment
        implements FragmentSettingsNavigation,
                BraveContentFilteringListener,
                BottomInsetViewProvider {
    private RecyclerView mRecyclerView;

    private ContentFilteringAdapter mAdapter;
    private FilterListAndroidHandler mFilterListAndroidHandler;
    private Value mFilterLists[];

    private void getFilterLists() {
        if (mFilterListAndroidHandler != null) {
            mFilterListAndroidHandler.getFilterLists(filterLists -> {
                mFilterLists = filterLists.storage;
                mAdapter.setFilterLists(mFilterLists);
            });
        }
    }

    public boolean onOptionsItemSelected(MenuItem item) {
        if (id == R.id.menu_id_edit) {
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

    @Override
    public void onDestroy() {
        if (mFilterListAndroidHandler != null) {
            mFilterListAndroidHandler.close();
            mFilterListAndroidHandler = null;
        }
        super.onDestroy();
    }
}
"""

ADAPTER = """    public void setFilterLists(Value filterLists[]) {
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
    assert PIN == "v1.99.54"
    with tempfile.TemporaryDirectory() as temporary:
        core = Path(temporary)
        files = {
            "components/brave_shields/core/browser/ad_block_component_service_manager.cc": MANAGER,
            "app/brave_main_delegate.cc": MAIN_DELEGATE,
            "android/java/org/chromium/chrome/browser/shields/ContentFilteringFragment.java": FRAGMENT,
            "android/java/org/chromium/chrome/browser/shields/ContentFilteringAdapter.java": ADAPTER,
        }
        for relative, content in files.items():
            path = core / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        apply_patches(core)
        verify_patches(core)
        before = {
            relative: (core / relative).read_text(encoding="utf-8")
            for relative in files
        }
        apply_patches(core)
        verify_patches(core)
        for relative, expected in before.items():
            assert (core / relative).read_text(encoding="utf-8") == expected, relative
    print("SANDIUM_ADBLOCK_UNIT_TEST=PASS source=v1.99.54 idempotent=true")


if __name__ == "__main__":
    main()
