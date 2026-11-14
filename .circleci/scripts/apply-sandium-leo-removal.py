#!/usr/bin/env python3
"""Pinned Leo compile-out transformations. Apply after UI overlays; shared billing separate."""
from pathlib import Path
import re,argparse

def end(s,a,left='{',right='}'):
 d=0
 for i in range(a,len(s)):
  if s[i]==left:d+=1
  elif s[i]==right:
   d-=1
   if d==0:return i+1
 raise RuntimeError('unbalanced '+s[a:a+80])

def block(s,anchor,replacement=''):
 a=s.find(anchor)
 if a<0:return s
 if s.count(anchor)!=1:raise RuntimeError('ambiguous '+anchor)
 b=s.index('{',a);return s[:a]+replacement+s[end(s,b):]

def method(s,name):
 match=re.search(r'(?m)^    (?:@Override\n    )?(?:public|private|protected)?[^\n;={}()]*\b'+name+r'\([^;{}]*?\)\s*\{',s)
 return block(s,match.group(0)) if match else s

def ifelse(s,anchor,keep_else=False):
 a=s.find(anchor)
 if a<0:return s
 b=s.index('{',a);z=end(s,b);m=re.match(r'\s*else\s*\{',s[z:])
 if m:
  eb=z+m.end()-1;ez=end(s,eb)
  return s[:a]+(s[eb+1:ez-1] if keep_else else '')+s[ez:]
 return s[:a]+s[z:]

def imports(s):return re.sub(r'^import [^\n]*(?:brave_leo|BraveLeo)[^\n]*\n','',s,flags=re.M)

A='android/java/org/chromium/chrome/browser/'
O='browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/'

def builder(s):
 s=imports(s);s=method(s,'setLeoAutocompleteDelegate');s=method(s,'isBraveLeoEnabled')
 s=block(s,'        if (isBraveLeoEnabled()')
 # These helpers only served Leo insertion/initialization, not normal suggestions.
 s=method(s,'getTileNavSuggestPosition')
 s=s.replace('            AutocompleteUIContext uiContext =\n                    createUIContext(context, host, textProvider, actionDelegate);\n','')
 s=s.replace('    @SuppressWarnings("UnusedVariable")\n    private AutocompleteUIContext createUIContext(', '    private AutocompleteUIContext createUIContext(')
 s=method(s,'createUIContext')
 s=s.replace('mLeoAutocompleteDelegate.isAutoCompleteEnabled(tab.getWebContents())','UserPrefs.get(tab.getProfile()).getBoolean(BravePref.AUTOCOMPLETE_ENABLED)')
 s=re.sub(r'^.*(?:mBraveLeoSuggestionProcessor|private BraveLeoAutocompleteDelegate mLeoAutocompleteDelegate)[^\n]*\n','',s,flags=re.M)
 return s

def apply(core):
 touched=[]
 def edit(rel,fn):
  p=core/rel;s=p.read_text();t=fn(s)
  if t!=s:p.write_text(t);touched.append(rel)
 # Exclusive source registrations are removed, not runtime-hidden.
 edit('android/brave_java_sources.gni',lambda s:re.sub(r'^.*(?:/brave_leo/|/BraveLeo)[^\n]*\n','',s,flags=re.M))
 edit('build/android/config.gni',lambda s:re.sub(r'^.*(?:/brave_leo/|components/ai_chat/core/common/mojom:mojom_java)[^\n]*\n','',s,flags=re.M))
 edit('android/java/AndroidManifest.xml',lambda s:re.sub(r'\s*<activity\b(?=[^>]*brave_leo\.BraveLeoPlansActivity)[^>]*(?:/>|>.*?</activity>)','',s,flags=re.S))
 edit('android/BUILD.gn',lambda s:re.sub(r'^.*"java/brave-res/(?:drawable/leo_|layout(?:-land)?/(?:activity_brave_leo|brave_leo)|xml/brave_leo)[^\n]*\n','',s,flags=re.M))
 edit('browser/android/BUILD.gn',lambda s:s.replace('    "//brave/browser/ai_chat",\n',''))
 def tabs(s):
  s=re.sub(r'^#include "brave/browser/ai_chat/[^\n]*\n','',s,flags=re.M)
  s=block(s,'  if (ai_chat::IsAllowedForContext(profile)) {')
  return s
 edit('browser/android/brave_tab_features.cc',tabs)
 def tabheader(s):
  s=block(s,'namespace ai_chat {')
  s=re.sub(r'^.*std::unique_ptr<ai_chat::[^\n]*\n','',s,flags=re.M)
  return s
 edit('browser/android/brave_tab_features.h',tabheader)
 def activity(s):
  s=imports(s)
  s=re.sub(r'^.*public static final String BRAVE_AI_CHAT_URL[^\n]*\n','',s,flags=re.M)
  s=s.replace('        maybeExecuteLeoVoicePrompt();\n','')
  s=s.replace('        } else if (id == R.id.brave_leo_id) {\n            openBraveLeo();','')
  s=method(s,'openBraveLeo');s=method(s,'maybeExecuteLeoVoicePrompt')
  s=block(s,'        if (!profile.isOffTheRecord()\n                && BraveLeoPrefUtils.isLeoEnabled()')
  s=ifelse(s,'        if (position == 0\n                && quickSearchEnginesModel.getType()',True)
  return s
 edit(A+'app/BraveActivity.java',activity)
 def prefs(s):
  s=imports(s);s=ifelse(s,'        if (BraveLeoPrefUtils.isLeoEnabled()) {')
  s=method(s,'checkLeoPolicyAndUpdatePreference')
  s=s.replace('        checkLeoPolicyAndUpdatePreference();\n','')
  s=block(s,'                    if (BraveLeoPrefUtils.isLeoDisabledByPolicy(profile)) {')
  return s
 edit(A+'settings/BraveMainPreferencesBase.java',prefs)
 def clear(s):
  s=imports(s);s=re.sub(r'^.*ClearBrowsingDataCheckBoxPreference mClearAIChat[^\n]*\n','',s,flags=re.M)
  s=s.replace('        getPreferenceScreen().addPreference(buildClearLeoAIHistory());\n','')
  s=method(s,'buildClearLeoAIHistory')
  s=block(s,'        if (mClearAIChatDataCheckBoxPreference != null')
  return s
 edit(A+'browsing_data/BraveClearBrowsingDataFragment.java',clear)
 def sync(s):
  s=re.sub(r'^.*private static final String PREF_SYNC_AI_CHAT[^\n]*\n','',s,flags=re.M)
  for indent in ('        ','                    '):s=block(s,'\n'+indent+'if (ChromeFeatureList.isEnabled(BraveFeatureList.BRAVE_SYNC_AI_CHAT)) {')
  return s
 edit(A+'sync/settings/BraveManageSyncSettings.java',sync)
 def appearance(s):
  s=imports(s)
  # Retain migration of an obsolete toolbar selection, not Leo feature code.
  s=s.replace('boolean isDisabled = BraveLeoPrefUtils.isLeoDisabledByPolicy(getProfile());','boolean isDisabled = true;')
  s=s.replace('        BraveRadioButtonGroupAdaptiveToolbarPreference.setLeoDisabledByPolicy(isDisabled);\n','')
  return s
 edit(A+'settings/AppearancePreferences.java',appearance)
 def adaptive(s):
  s=imports(s);a=s.find('        var leoButtonController =')
  if a>=0:
   z=s.index('AdaptiveToolbarButtonVariant.LEO, leoButtonController);',a)+len('AdaptiveToolbarButtonVariant.LEO, leoButtonController);')
   s=s[:a]+s[z:]
  return s
 edit(A+'ui/BraveAdaptiveToolbarUiCoordinator.java',adaptive)
 def mediator(s):
  s=imports(s)
  s=re.sub(r'^.*private static final String LEO_START_WORD_UPPER_CASE[^\n]*\n','',s,flags=re.M)
  s=s.replace('implements BraveSuggestionHost, BraveLeoAutocompleteDelegate','implements BraveSuggestionHost')
  s=s.replace('            ((BraveDropdownItemViewInfoListBuilder) mDropdownViewInfoListBuilder)\n                    .setLeoAutocompleteDelegate(this);\n','')
  for name in ('isAutoCompleteEnabled','isLeoEnabled','openLeoQuery','onVoiceResults'):s=method(s,name)
  return s
 edit(A+'omnibox/suggestions/BraveAutocompleteMediator.java',mediator)
 edit(O+'BraveDropdownItemViewInfoListBuilder.java',builder)
 def factory(s):
  s=imports(s)
  s=re.sub(r'        registerType\(\s*BraveOmniboxSuggestionUiType.BRAVE_LEO_SUGGESTION,.*?new BraveLeoSuggestionViewBinder\(\)\);','',s,flags=re.S)
  return s
 edit(O+'BraveOmniboxViewHolderFactory.java',factory)
 def widget(s):
  s=imports(s);s=method(s,'createLeoIntent')
  s=s.replace('updateAppWidgetsWithPolicy(\n                appWidgetIds,\n                BraveLeoPrefUtils.isLeoDisabledByPolicy(\n                        ProfileManager.getLastUsedRegularProfile()));','updateAppWidgetsWithPolicy(appWidgetIds);')
  s=s.replace('int[] appWidgetIds, boolean isLeoDisabledByPolicy','int[] appWidgetIds')
  s=s.replace('Context context, RemoteViews views, boolean isLeoDisabledByPolicy','Context context, RemoteViews views')
  s=s.replace('setSearchBarPendingIntent(context, views, isLeoDisabledByPolicy)','setSearchBarPendingIntent(context, views)')
  s=ifelse(s,'        if (BraveLeoPrefUtils.isLeoEnabled() && !isLeoDisabledByPolicy) {')
  return s
 edit(A+'widget/quickactionsearchandbookmark/QuickActionSearchAndBookmarkWidgetProvider.java',widget)
 def menu(s):
  s=imports(s);s=method(s,'buildBraveLeoItem')
  a=s.find('                new PolicyControlledMenuItem(\n                        R.id.brave_leo_id,')
  if a>=0:
   b=s.index('(',a);z=end(s,b,'(',')');z+=1 if s[z:z+1]==',' else 0;s=s[:a]+s[z:]
  return s
 edit(A+'tabbed_mode/BraveTabbedAppMenuPropertiesDelegate.java',menu)
 edit('browser/ui/android/omnibox/BUILD.gn',lambda s:re.sub(r'^.*(?:/brave_leo/|/BraveLeoAutocompleteDelegate)[^\n]*\n','',s,flags=re.M))
 def radio(s):
  s=method(s,'setLeoDisabledByPolicy')
  s=re.sub(r'^.*(?:private static boolean sLeoDisabledByPolicy|private @Nullable RadioButtonWithDescription mBraveLeoButton)[^\n]*\n','',s,flags=re.M)
  s=s.replace('        mBraveLeoButton =\n                (RadioButtonWithDescription) holder.findViewById(R.id.adaptive_option_brave_leo);\n','')
  s=block(s,'        if (!sIsJunitTesting\n                && mBraveLeoButton != null')
  s=s.replace('        } else if (mBraveLeoButton != null && mBraveLeoButton.isChecked()) {\n            mSelected = AdaptiveToolbarButtonVariant.LEO;\n            isOnCheckedChangedHandled = true;','')
  s=s.replace('            case AdaptiveToolbarButtonVariant.LEO:\n                return mBraveLeoButton;\n','')
  return s
 edit('browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/adaptive/settings/BraveRadioButtonGroupAdaptiveToolbarPreference.java',radio)
 def remove_xml(s,key):return re.sub(r'\s*<[^/>\s]+\b(?=[^>]*android:id="@\+id/'+key+r'")[^>]*/>','',s)
 edit('android/java/brave-res/layout/quick_action_search_and_bookmark_widget_layout.xml',lambda s:remove_xml(s,'ibLeo'))
 edit('browser/ui/android/toolbar/java/brave-res/layout/brave_adaptive_preference_buttons.xml',lambda s:remove_xml(s,'adaptive_option_brave_leo'))
 edit('android/java/brave-res/xml/brave_main_preferences.xml',lambda s:re.sub(r'\s*<org\.chromium\.components\.browser_ui\.settings\.ChromeBasePreference\b(?=[^>]*android:key="brave_leo")[^>]*/>','',s))
 edit('android/java/brave-res/layout/widget_search_preview.xml',lambda s:re.sub(r'\s*<ImageView\b(?=[^>]*search_widget_promo_leo_content_description)[^>]*/>','',s))
 print('\n'.join(touched))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);apply(p.parse_args().core)
