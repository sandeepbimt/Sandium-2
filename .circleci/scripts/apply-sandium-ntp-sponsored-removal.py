#!/usr/bin/env python3
"""Remove NTP sponsored processing paths, preserving ordinary wallpaper APIs.
Compatibility declarations/value types remain; this is not full type eradication.
"""
import argparse, hashlib, json, re
from pathlib import Path
MARKER = '// Sandium: sponsored NTP implementation removed; ordinary wallpapers retained.'
PINS = {'components/ntp_background_images/browser/ntp_background_images_service.cc': '5cae19919f293d64ef848e9b194978987bd6dc455f4b2cad2b74c5f0dafd9ce0', 'components/ntp_background_images/browser/view_counter_service.cc': '5c723490644406d1c69592607104213c4688bb10a306e5205e85615ff64cdff4', 'components/ntp_background_images/browser/BUILD.gn': '26c28f6a34bfb69000de6e59d70af3213c567d263b42e345692f0ba298a6eaa5', 'browser/ntp_background/view_counter_service_factory.cc': '0a383b17de0f3f5a96386f5f8a036808cf74db5dcd2063bd8624268d3a2c6b5e', 'components/ntp_background_images/browser/ntp_background_images_service.h': 'dabcc9d3fa3d34a6136b0ed45850b4e7619c8bc2ad0e604743d005a0809dd663', 'components/ntp_background_images/browser/view_counter_service.h': '849e7b81be2868efc791d2325ddb3fcf1c5f970cf27ea833154ce0a5f8c26599', 'components/ntp_background_images/browser/sponsored_content/new_tab_takeover/ntp_sponsored_content_data.cc': 'bfa2b68b40f24813ea7a010ac6887928ddb52b35b6397ca2e2b162a251db18e8', 'components/ntp_background_images/browser/sponsored_content/site/ntp_sponsored_sites_data.cc': '18a82ec4def99f911497531d06d3044c33747cca99b9de8e48cb57695d975f8b', 'components/ntp_background_images/browser/sponsored_content/new_tab_takeover/dynamic/ntp_dynamic_new_tab_takeover_ad_event_handler.cc': '82b28802b7d8d1e6366a76499990ca70427684144ee9df2a7b76c40a6d9ee45a', 'components/ntp_background_images/browser/sponsored_content/new_tab_takeover/dynamic/ntp_dynamic_new_tab_takeover_ad_event_handler.h': 'ec5f9f86681b87dc36458d8893132b0013631fc008f88d8eca116121420589b7', 'components/ntp_background_images/browser/sponsored_content/new_tab_takeover/new_tab_takeover_infobar_util.cc': 'aff98873c1357783d7ffe1c7d7147a77d66d5e1014b03f262f0d2483dee492e4', 'components/ntp_background_images/browser/view_counter_model.cc': 'bf95ff1e6b53d11726125a52f2946bccf1285cde56c4998e98656cfc41119104', 'components/ntp_background_images/browser/view_counter_model.h': '409d8c16db10940d0955ab04a9e38708ddc7e62876567fea8fa5b10192b7d04a'}
BASE='components/ntp_background_images/browser/'
EXCLUDED=(
 'sponsored_content/ntp_sponsored_content_source_util',
 'ntp_background_images_update_util',
 'sponsored_content/new_tab_takeover/static/sponsored_images_component_data',
 'sponsored_content/ntp_sponsored_images_component_installer',
 'sponsored_content/new_tab_takeover/static/ntp_static_new_tab_takeover_source',
 'sponsored_content/new_tab_takeover/dynamic/ntp_dynamic_new_tab_takeover_source',
 'sponsored_content/site/ntp_sponsored_site_image_source',
)

def body(s, qualified, replacement):
    # The pinned input is hash-verified before transformations. Find the unique
    # declaration (not a callback reference) and scan balanced C++ braces.
    matches=list(re.finditer(r'(?m)^[^\n;]*'+re.escape(qualified)+r'\(',s))
    if len(matches)!=1: raise ValueError('Function anchor mismatch: '+qualified)
    pos=s.index('{',matches[0].end()); depth=1; end=pos+1
    # All changed functions are pinned and contain no brace characters in
    # strings/comments except balanced lambda/function blocks.
    while depth:
        depth+=(s[end]=='{')-(s[end]=='}'); end+=1
    return s[:pos]+'{\n  // Sponsored NTP code is not part of Sandium.\n'+replacement+'\n}'+s[end:]

def transform(path,s):
    marker=MARKER.replace('//','#',1) if path.endswith('.gn') else MARKER
    if s.startswith(marker+'\n'): return s
    if hashlib.sha256(s.encode()).hexdigest()!=PINS[path]:
        raise ValueError('Pinned NTP source drift: '+path)
    if path==BASE+'view_counter_model.cc':
        for name in ('SetCampaignsTotalNewTabTakeoverCreativeCount','RegisterPageViewForNewTabTakeoverCreatives','MaybeResetNewTabTakeoverCount','ScheduleNextNewTabTakeoverCountReset','ResetNewTabTakeoverCountAndScheduleNextCountReset'):
            s=body(s,'ViewCounterModel::'+name,'')
        s=body(s,'ViewCounterModel::ShouldShowNewTabTakeover','  return false;')
        s=body(s,'ViewCounterModel::RegisterPageView','  RegisterPageViewForBackgroundImages();')
        s=body(s,'ViewCounterModel::RegisterPageViewForBackgroundImages','  RotateBackgroundWallpaperImageIndex();')
        s=body(s,'ViewCounterModel::Reset','  current_wallpaper_image_index_ = 0;\n  total_image_count_ = 0;')
        start=s.index('  // When browser is restarted');end=s.index('\n}',start)
        s=s[:start]+s[end:]
        s=s.replace('    : prefs_(prefs),\n      rand_int_inclusive_callback_(', '    : rand_int_inclusive_callback_(')
    elif path==BASE+'view_counter_model.h':
        start=s.index('  // For sponsored content.');end=s.index('  // For sponsored backgrounds.',start)
        s=s[:start]+s[end:]
        s=s.replace('    show_new_tab_takeover_wallpaper_ = show;','    // Sponsored wallpaper selection is absent.')
        s=s.replace('    return count_to_new_tab_takeover_wallpaper_;','    return 0;')
        s=s.replace('    count_to_new_tab_takeover_wallpaper_ = count;','    // Compatibility test setter has no state.')
        s=s.replace('    return show_new_tab_takeover_wallpaper_;','    return false;')
    elif path.endswith('ntp_dynamic_new_tab_takeover_ad_event_handler.cc'):
        start=s.index('namespace {\n');end=s.index('}  // namespace\n',start)+len('}  // namespace\n')
        s=s[:start]+s[end:]
        s=s.replace('    : ads_service_(ads_service) {}','    {}')
        s=body(s,'NTPDynamicNewTabTakeoverAdEventHandler::MaybeReportSponsoredContentAdEvent','')
    elif path.endswith('ntp_dynamic_new_tab_takeover_ad_event_handler.h'):
        s=s.replace('  const raw_ptr<brave_ads::AdsService> ads_service_ = nullptr;  // Not owned.\n','')
    elif path.endswith('new_tab_takeover_infobar_util.cc'):
        s=body(s,'ShouldDisplayNewTabTakeoverInfobar','  return false;')
        s=body(s,'RecordNewTabTakeoverInfobarWasDisplayed','')
        s=body(s,'SuppressNewTabTakeoverInfobar','')
    elif path.endswith('ntp_sponsored_content_data.cc'):
        s=compat_data('content', s[:s.index('#include')])
    elif path.endswith('ntp_sponsored_sites_data.cc'):
        s=compat_data('sites', s[:s.index('#include')])
    elif path==BASE+'view_counter_service.h':
        for text in (
            '  const raw_ptr<brave_ads::AdsService> ads_service_ = nullptr;\n',
            '  const raw_ptr<PrefService> local_state_ = nullptr;\n',
            '  bool is_supported_locale_ = false;\n',
            '  bool is_sponsored_images_component_registered_ = false;\n',
            '  base::WallClockTimer p3a_update_timer_;\n',
            '  std::unique_ptr<WeeklyStorage> new_tab_count_state_;\n',
            '  std::unique_ptr<DailyStorage> new_tab_count_daily_state_;\n',
            '  std::unique_ptr<WeeklyStorage> new_tab_takeover_count_state_;\n',
            '  base::ScopedObservation<brave_ads::AdsService, brave_ads::AdsServiceObserver>\n      ads_service_observation_{this};\n'):
            if s.count(text)!=1: raise ValueError('counter field drift')
            s=s.replace(text,'',1)
    elif path==BASE+'ntp_background_images_service.h':
        start=s.index('  base::WallClockTimer sponsored_images_update_check_timer_;')
        end=s.index('  base::ObserverList<Observer>::Unchecked observers_;',start)
        s=s[:start]+'  std::optional<std::string> sponsored_images_component_id_;\n\n'+s[end:]
        s=s.replace('  base::WeakPtrFactory<NTPBackgroundImagesService>\n      sponsored_images_weak_factory_{this};\n','')
    elif path==BASE+'BUILD.gn':
        for item in EXCLUDED:
            for ext in ('.cc','.h'):
                line='    "'+item+ext+'",\n'
                if s.count(line)!=1: raise ValueError('GN source missing '+item+ext)
                s=s.replace(line,'',1)
    elif path=='browser/ntp_background/view_counter_service_factory.cc':
        for cls in ('NTPStaticNewTabTakeoverSource','NTPDynamicNewTabTakeoverSource','NTPSponsoredSiteImageSource'):
            old='''    content::URLDataSource::Add(
        browser_context,
        std::make_unique<'''+cls+'''>(service));
'''
            if s.count(old)!=1: raise ValueError('URL source anchor '+cls)
            s=s.replace(old,'',1)
        s='\n'.join(line for line in s.split('\n') if not any('/'+item+'.h"' in line for item in EXCLUDED))
    elif path==BASE+'ntp_background_images_service.cc':
        s=body(s,'NTPBackgroundImagesService::Init','  RegisterBackgroundImagesComponent();')
        voids=('MaybeCheckForSponsoredComponentUpdate','ForceSponsoredComponentUpdate','ScheduleNextSponsoredImagesComponentUpdate','CheckSponsoredContentComponentUpdate','ResetSponsoredContentData','RegisterSponsoredImagesComponent','UnregisterSponsoredImagesComponent','AddSponsoredImagesOptedInProfile','RemoveSponsoredImagesOptedInProfile','OnVariationsCountryPrefChanged','OnSponsoredComponentReady','OnHandledSponsoredComponentData','OnHandledSponsoredSitesData')
        for name in voids:s=body(s,'NTPBackgroundImagesService::'+name,'')
        for name in ('GetNewTabTakeover','GetSponsoredSitesData'):
            s=body(s,'NTPBackgroundImagesService::'+name,'  return nullptr;')
        for name in ('MaybeGetSponsoredSiteImageFilePath','HandleSponsoredComponentData','HandleSponsoredSitesData'):
            s=body(s,'NTPBackgroundImagesService::'+name,'  return std::nullopt;')
        # Remove the excluded component installer header and campaign manifest constants.
        s='\n'.join(line for line in s.split('\n') if not any('/'+item+'.h"' in line for item in EXCLUDED))
        s=s.replace('constexpr char kNTPSponsoredManifestFile[] = "campaigns.json";\n','').replace('constexpr char kNTPSponsoredSitesManifestFile[] = "tiles.json";\n','')
    elif path==BASE+'view_counter_service.cc':
        voids=('ResetNotificationState','OnDidInitializeAdsService','OnDidClearAdsServiceData','RecordViewedAdEvent','RecordClickedAdEvent','DeprecatedOnSponsoredContentDidUpdate','OnSponsoredContentDidUpdate','ParseAndSaveNewTabPageAdsCallback','UpdateSponsoredImagesComponentRegistration','MaybeTriggerNewTabPageAdEvent','UpdateP3AValues')
        for name in voids:s=body(s,'ViewCounterService::'+name,'')
        for name in ('ShouldShowNewTabTakeover','CanShowNewTabTakeover','CanShowNewTabTakeoverWallpaper'):
            s=body(s,'ViewCounterService::'+name,'  return false;')
        s=body(s,'ViewCounterService::GetNewTabTakeover','  return nullptr;')
        for name in ('GetNewTabTakeoverWallpaper','GetNewTabTakeoverWallpaperFromAdsService','CheckNewTabTakeoverCreativeFileExists','OnCheckNewTabTakeoverCreativeFileExists','GetNewTabTakeoverWallpaperFromAdsServiceCallback'):
            s=body(s,'ViewCounterService::'+name,'  std::move(callback).Run(std::nullopt);')
        s=body(s,'ViewCounterService::OnGetNewTabTakeoverWallpaper','  std::move(callback).Run(GetNextWallpaperForDisplay());')
        s=body(s,'ViewCounterService::GetCurrentWallpaperForDisplay','  std::move(callback).Run(GetNextWallpaperForDisplay());')
        s=body(s,'ViewCounterService::ResetModel','''  model_.Reset();
  model_.set_show_new_tab_takeover_wallpaper(false);
  model_.set_show_wallpaper(IsShowBackgroundImageOptedIn());
  if (const auto* images = background_images_service_->GetBackgroundImagesData()) {
    model_.set_total_image_count(static_cast<int>(images->backgrounds.size()));
  }''')
        s=body(s,'ViewCounterService::OnPreferenceChanged','  ResetModel();')
        s=body(s,'ViewCounterService::RegisterPageView','  model_.RegisterPageView();')
        s=body(s,'ViewCounterService::Shutdown','  host_content_settings_map_observation_.Reset();\n  ntp_background_images_service_observation_.Reset();')
        for line in ('      ads_service_(ads_service),\n','      local_state_(local_state),\n','      is_supported_locale_(is_supported_locale),\n'):
            if s.count(line)!=1: raise ValueError('counter initializer drift')
            s=s.replace(line,'',1)
        # Remove observer hookup so old ad API cannot activate the no-op callbacks.
        start=s.index('  if (ads_service_) {'); end=s.index('\n  host_content_settings_map_observation_',start)
        s=s[:start]+s[end:]
        # No scheduled telemetry or sponsor counters; retain class fields/API ABI.
        start=s.index('  new_tab_count_state_ =');end=s.index('\n  ResetModel();',start)
        s=s[:start]+s[end:]
        start=s.index('  pref_change_registrar_.Add(\n      brave_rewards::prefs::kEnabled,')
        end=s.index('  pref_change_registrar_.Add(\n      prefs::kNewTabPageShowBackgroundImage,',start)
        s=s[:start]+s[end:]
        start=s.index('namespace {\n');end=s.index('}  // namespace\n',start)+len('}  // namespace\n')
        s=s[:start]+s[end:]
    return marker+'\n'+s

def apply(core):
    changed={p:transform(p,(core/p).read_text()) for p in PINS}
    # All transforms validated before writes; unknown pin is fatal.
    for p,text in changed.items():(core/p).write_text(text)
    print('SANDIUM_NTP_SPONSORED=installer_and_URL_sources_excluded processing_removed compatibility_types_retained')
def compat_data(kind, license_header):
    # Empty value compatibility only: no campaign parsing, filesystem checks,
    # URL construction, ad selection or telemetry implementation remains.
    prefix=license_header
    header='sponsored_content/new_tab_takeover/ntp_sponsored_content_data.h' if kind=='content' else 'sponsored_content/site/ntp_sponsored_sites_data.h'
    result=prefix+'#include "brave/'+BASE+header+'"\nnamespace ntp_background_images {\n'
    types=('Logo','Creative','Campaign','NTPSponsoredContentData') if kind=='content' else ('NTPSponsoredSitesData',)
    for t in types:
        result+=f'''{t}::{t}() = default;
{t}::{t}(const {t}&) = default;
{t}& {t}::operator=(const {t}&) = default;
{t}::{t}({t}&&) noexcept = default;
{t}& {t}::operator=({t}&&) noexcept = default;
{t}::~{t}() = default;
'''
    if kind=='sites':
        result+='''NTPSponsoredSitesData::NTPSponsoredSitesData(const base::DictValue&, const base::FilePath&, const std::string&) {}
bool NTPSponsoredSitesData::IsValid() const { return false; }
'''
    else:
        result+='''Creative::Creative(WallpaperType type, const base::FilePath& path, const gfx::Point& point, const Logo& value, const std::string& id)
 : wallpaper_type(type), file_path(path), focal_point(point), creative_instance_id(id), logo(value) {}
bool Campaign::IsValid() const { return false; }
NTPSponsoredContentData::NTPSponsoredContentData(const base::DictValue&, const base::FilePath&) {}
void NTPSponsoredContentData::ParseCampaigns(const base::ListValue&, const base::FilePath&) {}
bool NTPSponsoredContentData::IsValid() const { return false; }
const Creative* NTPSponsoredContentData::GetCreativeByInstanceId(const std::string&) const { return nullptr; }
std::optional<base::DictValue> NTPSponsoredContentData::MaybeGetBackgroundAt(size_t, size_t) const { return std::nullopt; }
std::optional<base::DictValue> NTPSponsoredContentData::MaybeGetBackground(const brave_ads::mojom::NewTabPageAdInfo&) { return std::nullopt; }
void FilterCampaigns(base::DictValue&, const base::FilePath&) {}
'''
    return result+'}  // namespace ntp_background_images\n'
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);a=p.parse_args();apply(a.core)
