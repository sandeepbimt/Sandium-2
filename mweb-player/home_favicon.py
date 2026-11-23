"""Persist native favicon results for explicitly saved RawS phone Home shortcuts only."""
import hashlib

BRIDGE_CC = 'chrome/browser/android/ntp/most_visited_sites_bridge.cc'
BRIDGE_JAVA = ('chrome/android/java/src/org/chromium/chrome/browser/'
               'suggestions/mostvisited/MostVisitedSitesBridge.java')
RENDERER = ('chrome/android/java/src/org/chromium/chrome/browser/'
            'suggestions/tile/TileRenderer.java')
STORE = 'components/ntp_tiles/custom_links_store.cc'
STORE_H = 'components/ntp_tiles/custom_links_store.h'
OWNERS = {BRIDGE_CC: 'e4fa5037720627c4b3ac83cc53308c6df8ef6996ce0b58cff12586854403c075'}
TRACKED = {
    BRIDGE_JAVA: 'f46f39f7afd4b77d54d5268b45179ef3f2ef415ec741f8e1256049d7ece35207',
    RENDERER: '8b0e8dd40d9d2940bcf688d0af4891fc8d385bcbbb36af965352a6fb7bbab73a',
    STORE: 'f1d239b3824433967d067c2369b77d761f1dba917e46f9571d12e4d715d93f9e',
    STORE_H: '49288027fdb0571ddb853ca4cf52562159665a9d1001cbe9f14fc622aaa051b0',
}

# Keep the owner's device/profile scope identical at tile ingress and JNI read/write.
PROFILE_GATE = '''bool IsRawSManualShortcutProfile(Profile* profile) {
  namespace device = base::android::device_info;
  return profile && !profile->IsOffTheRecord() &&
         base::android::apk_info::package_name() == "io.github.sandeepbimt.raws" &&
         !device::is_tablet() && !device::is_desktop() && !device::is_tv() &&
         !device::is_automotive() && !device::is_xr() && !device::is_foldable();
}

'''
NEW_JNI = '''static std::string JNI_MostVisitedSitesBridge_GetRawSManualFaviconTicket(
    Profile* profile, const GURL& url) {
  return IsRawSManualShortcutProfile(profile)
             ? ntp_tiles::CustomLinksStore::BeginRawSFaviconRead(profile->GetPrefs(), url)
             : std::string();
}

static std::string JNI_MostVisitedSitesBridge_GetRawSManualFavicon(
    Profile* profile, const GURL& url, const std::string& ticket) {
  return IsRawSManualShortcutProfile(profile)
             ? ntp_tiles::CustomLinksStore::ReadRawSFavicon(profile->GetPrefs(), url, ticket)
             : std::string();
}

static void JNI_MostVisitedSitesBridge_SaveRawSManualFavicon(
    Profile* profile, const GURL& url, const std::string& ticket,
    const std::string& encoded_png) {
  if (IsRawSManualShortcutProfile(profile)) {
    ntp_tiles::CustomLinksStore::WriteRawSFavicon(profile->GetPrefs(), url, ticket,
                                                 encoded_png);
  }
}

'''
STORE_POLICY = '''// This separate dictionary is deliberately not registered as syncable. Store
// only the display image of an explicit mobile shortcut, never site visits.
constexpr char kRawSManualFavicons[] = "raws.home.manual_shortcut_favicons";
constexpr char kRawSFaviconTicket[] = "ticket";
constexpr char kRawSFaviconImages[] = "icons";
constexpr size_t kMaxRawSFaviconEncodedLength = 64 * 1024;
constexpr size_t kMaxRawSFaviconCount = 32;
constexpr size_t kMaxRawSFaviconUrlLength = 2048;

bool IsRawSFaviconUrl(const GURL& url) {
  return url.is_valid() && url.SchemeIsHTTPOrHTTPS() && !url.has_username() &&
         !url.has_password() && url.spec().size() <= kMaxRawSFaviconUrlLength;
}

bool IsRawSManualLink(const PrefService* prefs, const GURL& url) {
  if (!IsRawSFaviconUrl(url)) {
    return false;
  }
  for (const auto& item : prefs->GetList(prefs::kCustomLinksListMobile)) {
    const auto* row = item.GetIfDict();
    if (!row) {
      continue;
    }
    const auto* key = row->FindString(kDictionaryKeyUrl);
    if (key && *key == url.spec() &&
        !row->FindBool(kDictionaryKeyIsMostVisited).value_or(false)) {
      return true;
    }
  }
  return false;
}

bool IsCurrentRawSFaviconTicket(const PrefService* prefs,
                               const std::string& ticket) {
  const auto* current =
      prefs->GetDict(kRawSManualFavicons).FindString(kRawSFaviconTicket);
  return !ticket.empty() && current && *current == ticket;
}

// Updating or clearing link identity revokes queued favicon responses. Never
// retain an image orphaned by delete/edit, even if Undo later recreates the URL.
void ReconcileRawSFavicons(PrefService* prefs,
                           const std::vector<CustomLinksManager::Link>& links) {
  const auto& old = prefs->GetDict(kRawSManualFavicons);
  if (old.empty()) {
    return;
  }
  base::DictValue retained;
  if (const auto* images = old.FindDict(kRawSFaviconImages)) {
    for (const auto& link : links) {
      if (retained.size() >= kMaxRawSFaviconCount) {
        break;
      }
      if (link.is_most_visited || !IsRawSFaviconUrl(link.url)) {
        continue;
      }
      const auto* icon = images->FindString(link.url.spec());
      if (icon && !icon->empty() && icon->size() <= kMaxRawSFaviconEncodedLength) {
        retained.Set(link.url.spec(), *icon);
      }
    }
  }
  base::DictValue current;
  current.Set(kRawSFaviconTicket, base::UnguessableToken::Create().ToString());
  current.Set(kRawSFaviconImages, std::move(retained));
  prefs->SetDict(kRawSManualFavicons, std::move(current));
}

'''
STORE_API = '''// static
std::string CustomLinksStore::BeginRawSFaviconRead(PrefService* prefs,
                                                  const GURL& url) {
  if (!prefs || !IsRawSManualLink(prefs, url)) {
    return {};
  }
  const auto& store = prefs->GetDict(kRawSManualFavicons);
  if (const auto* ticket = store.FindString(kRawSFaviconTicket)) {
    return *ticket;
  }
  const auto ticket = base::UnguessableToken::Create().ToString();
  ScopedDictPrefUpdate update(prefs, kRawSManualFavicons);
  update->Set(kRawSFaviconTicket, ticket);
  return ticket;
}

// static
std::string CustomLinksStore::ReadRawSFavicon(PrefService* prefs,
                                            const GURL& url,
                                            const std::string& ticket) {
  if (!prefs || !IsRawSManualLink(prefs, url) ||
      !IsCurrentRawSFaviconTicket(prefs, ticket)) {
    return {};
  }
  const auto* images = prefs->GetDict(kRawSManualFavicons).FindDict(kRawSFaviconImages);
  const auto* icon = images ? images->FindString(url.spec()) : nullptr;
  return (icon && icon->size() <= kMaxRawSFaviconEncodedLength) ? *icon
                                                              : std::string();
}

// static
void CustomLinksStore::WriteRawSFavicon(PrefService* prefs, const GURL& url,
                                      const std::string& ticket,
                                      const std::string& encoded_png) {
  if (!prefs || encoded_png.empty() ||
      encoded_png.size() > kMaxRawSFaviconEncodedLength ||
      !IsRawSManualLink(prefs, url) || !IsCurrentRawSFaviconTicket(prefs, ticket)) {
    return;
  }
  const auto* existing =
      prefs->GetDict(kRawSManualFavicons).FindDict(kRawSFaviconImages);
  if (existing) {
    const auto* old = existing->FindString(url.spec());
    if (old ? *old == encoded_png : existing->size() >= kMaxRawSFaviconCount) {
      return;
    }
  }
  ScopedDictPrefUpdate update(prefs, kRawSManualFavicons);
  update->EnsureDict(kRawSFaviconImages)->Set(url.spec(), encoded_png);
}

'''
STORE_DECL = '''  // Device-local sidecar for the explicit mobile list. The caller must use
  // the regular profile and restrict access to the manual-only RawS surface.
  static std::string BeginRawSFaviconRead(PrefService* prefs, const GURL& url);
  static std::string ReadRawSFavicon(PrefService* prefs,
                                    const GURL& url,
                                    const std::string& ticket);
  static void WriteRawSFavicon(PrefService* prefs,
                              const GURL& url,
                              const std::string& ticket,
                              const std::string& encoded_png);

'''
UI_BRIDGE = '''    public static String getRawSManualFaviconTicket(Profile profile, GURL url) {
        return MostVisitedSitesBridgeJni.get().getRawSManualFaviconTicket(profile, url);
    }

    public static String getRawSManualFavicon(Profile profile, GURL url, String ticket) {
        return MostVisitedSitesBridgeJni.get().getRawSManualFavicon(profile, url, ticket);
    }

    public static void saveRawSManualFavicon(
            Profile profile, GURL url, String ticket, String png) {
        MostVisitedSitesBridgeJni.get().saveRawSManualFavicon(profile, url, ticket, png);
    }

'''
UI_NATIVES = '''        @JniType("std::string")
        String getRawSManualFaviconTicket(
                @JniType("Profile*") Profile profile, @JniType("GURL") GURL url);

        @JniType("std::string")
        String getRawSManualFavicon(
                @JniType("Profile*") Profile profile,
                @JniType("GURL") GURL url,
                @JniType("std::string") String ticket);

        void saveRawSManualFavicon(
                @JniType("Profile*") Profile profile,
                @JniType("GURL") GURL url,
                @JniType("std::string") String ticket,
                @JniType("std::string") String png);

'''
TILE_CODEC = '''    private static final int RAWS_FAVICON_MAX_DIMENSION = 128;
    private static final int RAWS_FAVICON_MAX_PNG = 48 * 1024;
    private static final int RAWS_FAVICON_MAX_BASE64 = 64 * 1024;

    private static @Nullable Bitmap decodeRawSManualFavicon(String stored) {
        if (stored.isEmpty() || stored.length() > RAWS_FAVICON_MAX_BASE64) return null;
        try {
            byte[] png = Base64.decode(stored, Base64.NO_WRAP);
            if (png.length > RAWS_FAVICON_MAX_PNG) return null;
            BitmapFactory.Options bounds = new BitmapFactory.Options();
            bounds.inJustDecodeBounds = true;
            BitmapFactory.decodeByteArray(png, 0, png.length, bounds);
            if (!"image/png".equals(bounds.outMimeType)
                    || bounds.outWidth <= 0 || bounds.outHeight <= 0
                    || bounds.outWidth > RAWS_FAVICON_MAX_DIMENSION
                    || bounds.outHeight > RAWS_FAVICON_MAX_DIMENSION) return null;
            return BitmapFactory.decodeByteArray(png, 0, png.length);
        } catch (IllegalArgumentException invalid) {
            return null;
        }
    }

    private static String encodeRawSManualFavicon(Bitmap icon) {
        int edge = Math.max(icon.getWidth(), icon.getHeight());
        if (edge <= 0 || icon.isRecycled()) return "";
        Bitmap bounded = icon;
        if (edge > RAWS_FAVICON_MAX_DIMENSION) {
            float scale = (float) RAWS_FAVICON_MAX_DIMENSION / edge;
            bounded = Bitmap.createScaledBitmap(icon,
                    Math.max(1, Math.round(icon.getWidth() * scale)),
                    Math.max(1, Math.round(icon.getHeight() * scale)), true);
        }
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        if (!bounded.compress(Bitmap.CompressFormat.PNG, 100, bytes)
                || bytes.size() > RAWS_FAVICON_MAX_PNG) return "";
        return Base64.encodeToString(bytes.toByteArray(), Base64.NO_WRAP);
    }

'''
TILE_CONTEXT = '''        private final @Nullable Profile mRawSManualShortcutProfile;
        private final String mRawSFaviconTicket;
'''
TILE_BEGIN = '''            Profile profile = mProfile;
            mRawSManualShortcutProfile = profile != null && profile.isNativeInitialized()
                            && !profile.isOffTheRecord()
                            && "io.github.sandeepbimt.raws".equals(mContext.getPackageName())
                            && tile.getSource() == TileSource.CUSTOM_LINKS
                    ? profile : null;
            mRawSFaviconTicket = mRawSManualShortcutProfile != null
                    ? MostVisitedSitesBridge.getRawSManualFaviconTicket(
                            mRawSManualShortcutProfile, tile.getUrl())
                    : "";
'''
TILE_CALLBACK = '''                Profile profile = mRawSManualShortcutProfile;
                if (profile != null && profile == mProfile && profile.isNativeInitialized()
                        && !mRawSFaviconTicket.isEmpty()) {
                    if (icon == null) {
                        icon = decodeRawSManualFavicon(MostVisitedSitesBridge.getRawSManualFavicon(
                                profile, tile.getUrl(), mRawSFaviconTicket));
                        if (icon != null) iconType = IconType.FAVICON;
                    } else {
                        // Only a non-null bitmap from this existing native favicon callback
                        // can populate the sidecar. Never save generated letter fallbacks.
                        String png = encodeRawSManualFavicon(icon);
                        if (!png.isEmpty()) {
                            MostVisitedSitesBridge.saveRawSManualFavicon(
                                    profile, tile.getUrl(), mRawSFaviconTicket, png);
                        }
                    }
                }
'''


def transform(path, data):
    if (OWNERS | TRACKED).get(path) != hashlib.sha256(data).hexdigest():
        raise ValueError('wrong RawS Home favicon preimage: ' + path)
    s = data.decode()
    def edit(a, b):
        nonlocal s
        if s.count(a) != 1:
            raise ValueError(f'unexpected {path} anchor: {a}')
        s = s.replace(a, b, 1)

    if path == BRIDGE_CC:
        edit('#include <memory>\n', '#include <memory>\n#include <string>\n')
        edit('#include "components/ntp_tiles/metrics.h"',
             '#include "components/ntp_tiles/custom_links_store.h"\n#include "components/ntp_tiles/metrics.h"')
        edit('namespace {\n\nclass JavaHomepageClient', 'namespace {\n\n'+PROFILE_GATE+'class JavaHomepageClient')
        begin=s.index('  namespace device =',s.index('MostVisitedSitesBridge::MostVisitedSitesBridge'))
        end=s.index('  most_visited_->EnableTileTypes(',begin)
        edit(s[begin:end], '  const bool manual_shortcuts_only = IsRawSManualShortcutProfile(profile);\n')
        edit('DEFINE_JNI(MostVisitedSitesBridge)', NEW_JNI+'DEFINE_JNI(MostVisitedSitesBridge)')
    elif path == BRIDGE_JAVA:
        edit('    @NativeMethods\n', UI_BRIDGE+'    @NativeMethods\n')
        edit('    interface Natives {\n', '    interface Natives {\n'+UI_NATIVES)
    elif path == STORE_H:
        edit('#include <vector>', '#include <string>\n#include <vector>')
        edit('  // Register CustomLinksStore related prefs', STORE_DECL+'  // Register CustomLinksStore related prefs')
    elif path == STORE:
        edit('#include "base/strings/utf_string_conversions.h"',
             '#include "base/strings/utf_string_conversions.h"\n#include "base/unguessable_token.h"')
        edit('#include "components/prefs/pref_service.h"',
             '#include "components/prefs/pref_service.h"\n#include "components/prefs/scoped_user_pref_update.h"')
        edit('}  // namespace\n', STORE_POLICY+'}  // namespace\n')
        edit('  if (!has_recorded_first_load_stats) {', '''  if (custom_links_list_pref_ == prefs::kCustomLinksListMobile) {
    ReconcileRawSFavicons(prefs_, links);
  }

  if (!has_recorded_first_load_stats) {''')
        edit('  prefs_->SetList(custom_links_list_pref_, std::move(new_link_list));', '''  // Revoke in-flight icon writes before notifying any shortcut-list observers.
  if (custom_links_list_pref_ == prefs::kCustomLinksListMobile) {
    ReconcileRawSFavicons(prefs_, links);
  }
  prefs_->SetList(custom_links_list_pref_, std::move(new_link_list));''')
        edit('  prefs_->ClearPref(custom_links_list_pref_);', '''  if (custom_links_list_pref_ == prefs::kCustomLinksListMobile) {
    prefs_->ClearPref(kRawSManualFavicons);
  }
  prefs_->ClearPref(custom_links_list_pref_);''')
        edit('// static\nvoid CustomLinksStore::RegisterProfilePrefs(', STORE_API+'// static\nvoid CustomLinksStore::RegisterProfilePrefs(')
        edit('  user_prefs->RegisterListPref(prefs::kCustomLinksList,', '''  user_prefs->RegisterDictionaryPref(kRawSManualFavicons);
  user_prefs->RegisterListPref(prefs::kCustomLinksList,''')
    elif path == RENDERER:
        edit('import android.graphics.Bitmap;', 'import android.graphics.Bitmap;\nimport android.graphics.BitmapFactory;')
        edit('import android.view.KeyEvent;', 'import android.util.Base64;\nimport android.view.KeyEvent;')
        edit('import org.chromium.chrome.browser.suggestions.SuggestionsConfig.TileStyle;',
             'import org.chromium.chrome.browser.suggestions.SuggestionsConfig.TileStyle;\n'
             'import org.chromium.chrome.browser.suggestions.mostvisited.MostVisitedSitesBridge;')
        edit('import java.lang.ref.WeakReference;',
             'import java.io.ByteArrayOutputStream;\nimport java.lang.ref.WeakReference;')
        edit('    private class LargeIconCallbackImpl', TILE_CODEC+'    private class LargeIconCallbackImpl')
        edit('        private final Runnable mLoadCompleteCallback;\n',
             '        private final Runnable mLoadCompleteCallback;\n'+TILE_CONTEXT)
        edit('            mLoadCompleteCallback = loadCompleteCallback;\n',
             '            mLoadCompleteCallback = loadCompleteCallback;\n'+TILE_BEGIN)
        edit('                tile.setIconType(iconType);\n', TILE_CALLBACK+'                tile.setIconType(iconType);\n')
    return s.encode()
