#!/usr/bin/env python3
"""Browser-owned element chooser source only; NOT a pipeline entry point."""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
PACKAGE='org/chromium/chrome/browser/sandium/dark/SandiumElementColorsUtils.java'
HANDLER='android/java/org/chromium/chrome/browser/shields/BraveUnifiedPanelHandler.java'
LAYOUT='android/java/brave-res/layout/brave_shields_tab_content.xml'
A='{http://schemas.android.com/apk/res/android}'
ET.register_namespace('android',A[1:-1]);ET.register_namespace('app','http://schemas.android.com/apk/res-auto');ET.register_namespace('tools','http://schemas.android.com/tools')
def insert(text,anchor,entry):
 if entry in text:return text
 if text.count(anchor)!=1:raise ValueError('Element chooser anchor changed: '+anchor)
 return text.replace(anchor,anchor+entry,1)
def handler(text):
 if 'SandiumElementColorsUtils.start(' in text:
  start=text.index('        View correctColors =')
  end=text.index('        }',text.index('            });',start))+10
  block=text[start:end].replace('Context context = mContext;', 'Context correctionContext = mContext;').replace('context == null', 'correctionContext == null').replace('                        context, selectedTab);','                        correctionContext, selectedTab);')
  guard="""                if (!Boolean.TRUE.equals(org.chromium.chrome.browser.night_mode.SandiumDarkPages
                        .enabled(selectedTab.getWebContents(), selectedTab.getUrl()))) return;"""
  if guard not in block:
   block=block.replace('                hide();',guard+'\n                hide();')
  return text[:start]+block+text[end:]
 return insert(text,'        setupAdvancedOptionsListeners();\n','''        View correctColors = popupView.findViewById(R.id.sandium_element_colors_button);
        if (correctColors != null) {
            correctColors.setOnClickListener(v -> {
                Context correctionContext = mContext;
                Tab selectedTab = mCurrentTab;
                if (correctionContext == null || selectedTab == null) return;
                if (!Boolean.TRUE.equals(org.chromium.chrome.browser.night_mode.SandiumDarkPages
                        .enabled(selectedTab.getWebContents(), selectedTab.getUrl()))) return;
                hide(); // The page must receive the user's element selection.
                org.chromium.chrome.browser.sandium.dark.SandiumElementColorsUtils.start(
                        correctionContext, selectedTab);
            });
        }
''')
def layout(text):
 if '@+id/sandium_element_colors_button' in text:return regroup(text)
 if 'SANDIUM_GROUPED_POPUP_V1' not in text:raise ValueError('Grouped Shield popup must be composed first')
 root=ET.fromstring(text);view=ET.Element('TextView')
 for k,v in {'id':'@+id/sandium_element_colors_button','layout_width':'match_parent','layout_height':'wrap_content','minHeight':'48dp','paddingHorizontal':'16dp','paddingVertical':'12dp','layout_marginTop':'10dp','gravity':'center_vertical','background':'@drawable/advanced_options_bg','text':'@string/sandium_element_title','textSize':'16sp','textColor':'?attr/colorOnSurface','clickable':'true','focusable':'true'}.items():view.set(A+k,v)
 root.insert(3,view);ET.indent(root,space='    ')
 return regroup(text[:text.index('<LinearLayout')]+ET.tostring(root,encoding='unicode')+'\n')
def regroup(text):
 root=ET.fromstring(text)
 def node(name):
  return next(e for e in root.iter() if e.get(A+'id')=='@+id/'+name)
 def detach(e):
  for parent in root.iter():
   if e in list(parent):parent.remove(e);return e
 appearance=[detach(node(n)) for n in ('sandium_dark_pages_button','sandium_element_colors_button')]
 controls=node('advanced_options_content')
 privacy=[detach(node(n)) for n in ('trackers_item','block_element_item','clear_blocked_elements_divider','clear_blocked_elements_button')]
 data=[detach(node(n)) for n in ('cookies_item','shred_data_item')]
 for e in list(root):
  if e.get(A+'id')=='@+id/sandium_appearance_group':root.remove(e)
 for e in list(controls):controls.remove(e)
 def card(children):
  c=ET.Element('LinearLayout')
  for k,v in {'layout_width':'match_parent','layout_height':'wrap_content','orientation':'vertical','layout_marginTop':'10dp','background':'@drawable/advanced_options_bg','clipToOutline':'true'}.items():c.set(A+k,v)
  for e in children:
   if e in appearance:
    e.attrib.pop(A+'background',None);e.attrib.pop(A+'layout_marginTop',None)
   c.append(e)
  return c
 c=card(appearance);c.set(A+'id','@+id/sandium_appearance_group');root.insert(2,c)
 controls.append(card(privacy));controls.append(card(data))
 ET.indent(root,space='    ')
 return text[:text.index('<LinearLayout')]+ET.tostring(root,encoding='unicode')+'\n'
def plan(core):
 gni=core/'android/brave_java_sources.gni';build=core/'android/BUILD.gn';jni=core/'build/android/config.gni'
 return {core/HANDLER:handler((core/HANDLER).read_text()),core/LAYOUT:layout((core/LAYOUT).read_text()),
 core/'android/java'/PACKAGE:(HERE/'java'/PACKAGE).read_text(),
 core/'android/java/brave-res/values/sandium_element_colors_strings.xml':(HERE/'res/values/sandium_element_colors_strings.xml').read_text(),
 jni:insert(jni.read_text(),'brave_jni_headers_sources = [\n','  "//brave/android/java/'+PACKAGE+'",\n'),
 gni:insert(gni.read_text(),'brave_java_sources = [\n','  "../../brave/android/java/'+PACKAGE+'",\n'),
 build:insert(build.read_text(),'    "java/brave-res/values/brave_ids.xml",\n','    "java/brave-res/values/sandium_element_colors_strings.xml",\n')}
def apply(core):
 outputs=plan(core)
 for path,text in outputs.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('core',type=Path);apply(p.parse_args().core)
