"""Paint-only Shields detail/tooltip rim; no Java, policies or hit targets."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
A='{http://schemas.android.com/apk/res/android}'
ET.register_namespace('android', A[1:-1])
DETAILS=('brave_trackers_ads_panel.xml','brave_cookies_panel.xml','brave_shred_data_panel.xml','brave_https_upgrade_panel.xml','brave_report_broken_site_panel.xml')
BASE='android/java/brave-res/'
def detail(source):
    # Alter only the root background: the shared panel already owns the rim.
    match=re.search(r'<(?:LinearLayout|ScrollView)\b[^>]*>', source)
    if not match: raise ValueError('Unknown Shields detail root')
    old='android:background="?attr/colorSurfaceContainer"'
    new='android:background="@android:color/transparent"'
    tag=match.group()
    if new in tag:return source
    if tag.count(old)!=1:raise ValueError('Unknown Shields detail background')
    return source[:match.start()]+tag.replace(old,new)+source[match.end():]
def tooltip(source):
    if 'SANDIUM_TOOLTIP_TAPERED_RIM' in source:return source
    root=ET.fromstring(source)
    if root.tag!='shape' or root.find('solid').get(A+'color')!='@color/sandium_shields_tooltip_surface' or root.find('corners').get(A+'radius')!='16dp':
        raise ValueError('Expected themed Shields tooltip')
    layers=ET.Element('layer-list',{A+'paddingMode':'stack',**{A+'padding'+x:'0dp' for x in ('Left','Top','Right','Bottom')}})
    # One theme surface/radius anchor keeps native-theme replay idempotent.
    item=ET.SubElement(layers,'item')
    shape=ET.SubElement(item,'shape',{A+'shape':'rectangle'})
    ET.SubElement(shape,'solid',{A+'color':'@color/sandium_shields_tooltip_surface'})
    ET.SubElement(shape,'corners',{A+'radius':'16dp'})
    for i,shade in enumerate(('#507D8085','#287D8085','#107D8085'),1):
        item=ET.SubElement(layers,'item',{A+x:str(i)+'dp' for x in ('left','top','right','bottom')})
        shape=ET.SubElement(item,'shape',{A+'shape':'rectangle'})
        ET.SubElement(shape,'stroke',{A+'width':'1dp',A+'color':shade})
        ET.SubElement(shape,'corners',{A+'radius':str(16-i)+'dp'})
    ET.indent(layers,space='    ')
    return '<?xml version="1.0" encoding="utf-8"?>\n'+'\n'.join(re.findall(r'<!--.*?-->',source,re.S))+'\n<!-- SANDIUM_TOOLTIP_TAPERED_RIM: native pointer remains separate and unchanged. -->\n'+ET.tostring(layers,encoding='unicode')+'\n'
def plan(core):
    result={core/BASE/'layout'/name:detail((core/BASE/'layout'/name).read_text()) for name in DETAILS}
    p=core/BASE/'drawable/shields_tooltip_background.xml'
    result[p]=tooltip(p.read_text())
    return result
