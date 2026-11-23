"""RawS Android phone Home: only explicitly stored shortcuts, never starters."""

import hashlib

OWNERS = {
    'chrome/browser/android/ntp/most_visited_sites_bridge.cc':
        '88ab76cbc26cc86232ccda692d2ab0b93154b72b6829bc39f33bac19ba884fd9',
    'components/ntp_tiles/most_visited_sites.cc':
        '9acfa6b5d78a669e7b8ba2b0b2bfc0f6ffd721e073c0f481fe517f289938fd55',
    'components/ntp_tiles/most_visited_sites.h':
        'bdb9f31fbfaf1af1360e1240f8987291aaa3b5a1931f22715280abd11000b423',
    'components/ntp_tiles/custom_links_manager.h':
        'ab6496123b8378160e3bdf792a58c46fe1816a91712c5c447cfece7c140a8a18',
    'components/ntp_tiles/custom_links_manager_impl.cc':
        '96363b912790cfb07b78bcfc9cf9155150a0df4f121a43f722b9f74d581a4cf8',
    'components/ntp_tiles/custom_links_manager_impl.h':
        '688c4c897e0f5994cc859876a054bb75086c247d8352bc610097f1ce38297d6a',
}
BRIDGE, SITES, SITES_H, MANAGER_H, STORE, STORE_H = OWNERS


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Unexpected shortcut source anchor: {old[:120]!r}')
    return text.replace(old, new, 1)


def transform(path: str, data: bytes) -> bytes:
    if OWNERS.get(path) != hashlib.sha256(data).hexdigest():
        raise ValueError(f'Unexpected shortcut source preimage: {path}')
    text = data.decode('utf-8')

    def edit(old, new):
        nonlocal text
        text = once(text, old, new)

    if path == BRIDGE:
        edit('#include "base/android/jni_android.h"',
             '#include "base/android/apk_info.h"\n#include "base/android/device_info.h"\n'
             '#include "base/android/jni_android.h"')
        edit('''  most_visited_->EnableTileTypes(
      ntp_tiles::MostVisitedSites::EnableTileTypesOptions()
          .with_top_sites(true)
          .with_custom_links(true));''', '''  // Both the displayed native Home and its explicit menu Add use this bridge.
  namespace device = base::android::device_info;
  const bool manual_shortcuts_only =
      !profile->IsOffTheRecord() &&
      base::android::apk_info::package_name() == "io.github.sandeepbimt.raws" &&
      !device::is_tablet() && !device::is_desktop() && !device::is_tv() &&
      !device::is_automotive() && !device::is_xr() && !device::is_foldable();
  most_visited_->EnableTileTypes(
      ntp_tiles::MostVisitedSites::EnableTileTypesOptions()
          .with_top_sites(!manual_shortcuts_only)
          .with_custom_links(true)
          .with_manual_custom_links_only(manual_shortcuts_only));''')
    elif path == SITES_H:
        edit('    bool operator==(const EnableTileTypesOptions&) const = default;', '''    EnableTileTypesOptions& with_manual_custom_links_only(bool enabled) {
      manual_custom_links_only = enabled;
      return *this;
    }

    bool operator==(const EnableTileTypesOptions&) const = default;''')
        edit('    bool enable_enterprise_shortcuts = false;', '''    bool enable_enterprise_shortcuts = false;
    bool manual_custom_links_only = false;''')
    elif path == SITES:
        edit('''    if (popular_sites_ && NeedPopularSites(prefs_, GetMaxNumSites())) {''',
             '''    if (!enabled_tile_types_.manual_custom_links_only && popular_sites_ &&
        NeedPopularSites(prefs_, GetMaxNumSites())) {''')
        edit('''    if (top_sites_) {
      // Register as TopSitesObserver''', '''    if (!enabled_tile_types_.manual_custom_links_only && top_sites_) {
      // Register as TopSitesObserver''')
        edit('''void MostVisitedSites::Refresh() {
  if (top_sites_) {''', '''void MostVisitedSites::Refresh() {
  if (!enabled_tile_types_.manual_custom_links_only && top_sites_) {''')
        edit('''  if (IsTopSitesEnabled()) {
    // Custom Tiles can mix with other tiles: Initialize as empty list.''', '''  if (enabled_tile_types_.manual_custom_links_only || IsTopSitesEnabled()) {
    // Manual-only starts empty, even for the Add bridge with no observers.
    // Mixed mode also creates an empty explicit shortcut list.''')
        edit('''    enabled_tile_types_ = options;
    BuildCurrentTiles''', '''    enabled_tile_types_ = options;
    if (options.manual_custom_links_only && custom_links_manager_) {
      custom_links_manager_->SetManualLinksOnly();
    }
    BuildCurrentTiles''')
        edit('''    const CustomLinksManager::Link& link = links.at(i);
#if''', '''    const CustomLinksManager::Link& link = links.at(i);
    if (enabled_tile_types_.manual_custom_links_only && link.is_most_visited) {
      continue;
    }
#if''')
        edit('''bool MostVisitedSites::ShouldQueryTopSites() const {
  return IsTopSitesEnabled() ||''', '''bool MostVisitedSites::ShouldQueryTopSites() const {
  if (enabled_tile_types_.manual_custom_links_only) {
    return false;
  }
  return IsTopSitesEnabled() ||''')
    elif path == MANAGER_H:
        edit('  virtual ~CustomLinksManager() = default;', '''  virtual ~CustomLinksManager() = default;

  // Optional policy for a dedicated manual-only surface. Implementations
  // should exclude automatic imports from the editable list and capacity.
  virtual void SetManualLinksOnly() {}''')
    elif path == STORE_H:
        edit('  bool Initialize(const NTPTilesVector& tiles) override;', '''  void SetManualLinksOnly() override;
  bool Initialize(const NTPTilesVector& tiles) override;''')
        edit('  CustomLinksStore store_;', '''  CustomLinksStore store_;
  bool manual_links_only_ = false;''')
    elif path == STORE:
        edit('''bool CustomLinksManagerImpl::Initialize(const NTPTilesVector& tiles) {''', '''void CustomLinksManagerImpl::SetManualLinksOnly() {
  // Invoked before this bridge observes/publishes tiles. Do not write prefs
  // just for opening Home; the next explicit shortcut edit uses this list.
  manual_links_only_ = true;
  std::erase_if(current_links_,
                [](const Link& link) { return link.is_most_visited; });
  previous_links_ = std::nullopt;
}

bool CustomLinksManagerImpl::Initialize(const NTPTilesVector& tiles) {''')
        edit('''  for (const NTPTile& tile : tiles) {
    current_links_.emplace_back(Link{tile.url, tile.title, true});
  }''', '''  if (!manual_links_only_) {
    for (const NTPTile& tile : tiles) {
      current_links_.emplace_back(Link{tile.url, tile.title, true});
    }
  }''')
        edit('''  if (!IsInitialized() || deletion_info.is_from_expiration()) {''',
             '''  if (manual_links_only_ || !IsInitialized() || deletion_info.is_from_expiration()) {''')
        edit('''  if (IsInitialized()) {
    current_links_ = store_.RetrieveLinks();
  } else {
    current_links_.clear();
  }''', '''  if (IsInitialized()) {
    current_links_ = store_.RetrieveLinks();
    if (manual_links_only_) {
      std::erase_if(current_links_,
                    [](const Link& link) { return link.is_most_visited; });
    }
  } else {
    current_links_.clear();
  }''')
    return text.encode('utf-8')
