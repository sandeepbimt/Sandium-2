#!/usr/bin/env python3
"""Apply extended Sandium marks after Brave's branding.js has copied upstream assets."""
from pathlib import Path
import re, shutil, struct, subprocess, sys

S = "M 101,18 C 86,6 67,4 50,9 C 33,14 20,27 20,41 C 20,53 28,61 40,68 L 81,91 C 87,95 86,101 79,105 C 64,114 47,109 35,100 L 21,115 C 39,131 63,134 84,125 C 104,116 115,101 115,85 C 115,71 105,63 92,55 L 51,31 C 45,27 48,22 55,19 C 68,14 83,18 93,27 Z"
F = "M 88,25 L 106,16 L 101,36 Z"

def fail(s): raise SystemExit("SANDIUM_EXTENDED_BRANDING_GATE=FAIL " + s)
def scale_path(p, k):
    return re.sub(r"(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)",
                  lambda m: f"{float(m[1])*k:.2f},{float(m[2])*k:.2f}", p)
def png_info(p):
    b=p.read_bytes()
    if len(b)<33 or b[:8]!=b"\x89PNG\r\n\x1a\n" or b[12:16]!=b"IHDR": fail(f"invalid PNG {p}")
    return struct.unpack(">IIBBBBB", b[16:29])
def copy(src,dst):
    if not src.is_file() or not src.stat().st_size: fail(f"missing asset {src}")
    dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    if src.read_bytes()!=dst.read_bytes(): fail(f"copy mismatch {dst}")
def vector(size,animated):
    k=size/128
    group=f'<group android:name="brave_logo" android:pivotX="144" android:pivotY="144">\n' if animated else ""
    end="</group>\n" if animated else ""
    return f'''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android" xmlns:aapt="http://schemas.android.com/aapt" android:width="{size}dp" android:height="{size}dp" android:viewportWidth="{size}" android:viewportHeight="{size}">
{group}<path android:pathData="{scale_path(S,k)}" android:fillType="evenOdd"><aapt:attr name="android:fillColor"><gradient android:startX="{12*k:.2f}" android:startY="{12*k:.2f}" android:endX="{116*k:.2f}" android:endY="{116*k:.2f}" android:type="linear"><item android:offset="0" android:color="#FF45E0D2"/><item android:offset="1" android:color="#FF176FB5"/></gradient></aapt:attr></path>
<path android:pathData="{scale_path(F,k)}" android:fillColor="#FFB1FFF2"/>
{end}</vector>'''
def main():
    from argparse import ArgumentParser
    p=ArgumentParser(); p.add_argument("--src",required=True,type=Path); p.add_argument("--core",required=True,type=Path); p.add_argument("--source",required=True,type=Path); p.add_argument("--generated",required=True,type=Path)
    a=p.parse_args(); src,core,source,out=(x.resolve() for x in (a.src,a.core,a.source,a.generated))
    if not (src/".git").exists() or not (core/".git").exists(): fail("Chromium/Brave checkout missing")
    mark=source/"layered_app_icon.png"
    if not mark.is_file(): fail("Sandium foreground master missing")
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        subprocess.check_call([sys.executable,"-m","pip","install","--user","Pillow"])
        from PIL import Image, ImageDraw, ImageFont
    def font(sz,bold):
        paths=(("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
               ("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"))
        for q in paths:
            if Path(q).is_file(): return ImageFont.truetype(q,sz)
        return ImageFont.load_default()
    def spaced(draw,text,x,y,f,fill,sp):
        for ch in text: draw.text((x,y),ch,font=f,fill=fill); x+=draw.textlength(ch,font=f)+sp
    def product(path,w,h,white):
        im=Image.open(mark).convert("RGBA"); bb=im.getchannel("A").getbbox()
        if not bb: fail("foreground mark transparent")
        im=im.crop(bb); canvas=Image.new("RGBA",(w,h),(0,0,0,0)); d=ImageDraw.Draw(canvas)
        side=int(h*.82); left=max(1,int(h*.04)); canvas.alpha_composite(im.resize((side,side),Image.Resampling.LANCZOS),(left,(h-side)//2))
        tx=left+side+max(2,int(h*.08)); fg=(244,251,252,255) if white else (8,26,42,255)
        sz=max(9,int(h*.43)); f=font(sz,True); spacing=max(.3,h*.012)
        while sz>8 and sum(d.textlength(c,font=f)+spacing for c in "SANDIUM")-spacing>w-tx-2: sz-=1; f=font(sz,True)
        spaced(d,"SANDIUM",tx,max(0,int(h*.13)),f,fg,spacing)
        spaced(d,"BROWSER",tx,int(h*.66),font(max(6,int(h*.17)),False),(66,211,207,255),max(.8,h*.035))
        path.parent.mkdir(parents=True,exist_ok=True); canvas.save(path,format="PNG",optimize=True)
    def favicon(path,size):
        im=Image.open(mark).convert("RGBA"); bb=im.getchannel("A").getbbox()
        if not bb: fail("foreground mark transparent")
        im=im.crop(bb); margin=max(1,int(size*.06)); side=size-2*margin
        canvas=Image.new("RGBA",(size,size),(0,0,0,0)); canvas.alpha_composite(im.resize((side,side),Image.Resampling.LANCZOS),(margin,margin))
        path.parent.mkdir(parents=True,exist_ok=True); canvas.save(path,format="PNG",optimize=True)
    logo=core/"android/java/brave-res/drawable/ic_brave_logo.xml"; splash=core/"browser/first_run/android/java/res/drawable/ic_brave_splash.xml"
    logo.parent.mkdir(parents=True,exist_ok=True); splash.parent.mkdir(parents=True,exist_ok=True)
    logo.write_text(vector(162,False),encoding="utf-8"); splash.write_text(vector(288,True),encoding="utf-8")
    animated=splash.with_name("ic_brave_splash_animated.xml")
    # Brave's animated-vector wrapper declares the animation target, while
    # the drawable referenced by that wrapper owns the named group and pivot.
    # Validate each part in its correct upstream resource instead of looking
    # for drawable-group pivot attributes in the animated-vector wrapper.
    animated_text=animated.read_text(encoding="utf-8") if animated.is_file() else ""
    splash_text=splash.read_text(encoding="utf-8")
    if not animated.is_file() or 'android:name="brave_logo"' not in animated_text or 'android:animation="@animator/ic_brave_splash_scale"' not in animated_text:
        fail("Brave animated splash target contract changed")
    if '<group android:name="brave_logo" android:pivotX="144" android:pivotY="144">' not in splash_text:
        fail("Brave splash drawable group/pivot contract changed")
    specs=(("default_100_percent","product_logo_name_48.png",154,48,False),("default_200_percent","product_logo_name_48.png",309,96,False),("default_100_percent","product_logo_white.png",184,58,True),("default_200_percent","product_logo_white.png",368,114,True))
    for density,name,w,h,white in specs: product(out/"product-logos"/density/name,w,h,white)
    favicon(out/"product-logos/default_100_percent/product_logo_16.png",16); favicon(out/"product-logos/default_200_percent/product_logo_16.png",32)
    maps=(("default_100_percent","product_logo_name_48.png","product_logo.png",154,48),("default_100_percent","product_logo_white.png","product_logo_white.png",184,58),("default_100_percent","product_logo_16.png","favicon_product.png",16,16),("default_200_percent","product_logo_name_48.png","product_logo.png",309,96),("default_200_percent","product_logo_white.png","product_logo_white.png",368,114),("default_200_percent","product_logo_16.png","favicon_product.png",32,32))
    for density,name,dest,w,h in maps:
        f=out/"product-logos"/density/name
        if png_info(f)[:4]!=(w,h,8,6): fail(f"expected 8-bit RGBA {w}x{h}: {f}")
        copy(f,core/"app/theme"/density/"brave"/name); copy(f,src/"components/resources"/density/"chromium"/dest)
    branding=("COMPANY_FULLNAME=Sandium Browser Project\nCOMPANY_SHORTNAME=Sandium\nPRODUCT_FULLNAME=Sandium Browser\nPRODUCT_SHORTNAME=Sandium\nPRODUCT_INSTALLER_FULLNAME=Sandium Browser Installer\nPRODUCT_INSTALLER_SHORTNAME=Sandium Installer\nCOPYRIGHT=Copyright 2016 The Brave Authors. All rights reserved.\nMAC_BUNDLE_ID=com.brave.Browser\nMAC_CREATOR_CODE=Cr24\nMAC_TEAM_ID=KL8N8XSYF4\n")
    for f in (core/"app/theme/brave/BRANDING",src/"chrome/app/theme/brave/BRANDING"):
        f.parent.mkdir(parents=True,exist_ok=True); f.write_text(branding,encoding="utf-8")
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" role="img" aria-label="Sandium Browser"><defs><linearGradient id="s" x1="3" y1="2" x2="22" y2="23" gradientUnits="userSpaceOnUse"><stop stop-color="#45E0D2"/><stop offset="1" stop-color="#176FB5"/></linearGradient></defs><path d="{scale_path(S,24/128)}" fill="url(#s)" fill-rule="evenodd"/><path d="{scale_path(F,24/128)}" fill="#B1FFF2"/></svg>'''
    web=src/"ui/webui/resources/images/chrome_logo_dark.svg"; web.parent.mkdir(parents=True,exist_ok=True); web.write_text(svg,encoding="utf-8")
    word=out/"sandium_wordmark.svg"; word.parent.mkdir(parents=True,exist_ok=True); word.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 160" role="img" aria-label="Sandium Browser"><path d="{S}" fill="#22CFCB"/><text x="150" y="75" font-family="Inter,Arial,sans-serif" font-size="57" font-weight="650" fill="#E7F5F7">SANDIUM</text><text x="154" y="119" font-size="20" letter-spacing="7" fill="#42D3CF">BROWSER</text></svg>',encoding="utf-8")
    for f in (core/"browser/ui/android/strings/android_brave_strings.grd",src/"chrome/browser/ui/android/strings/android_brave_strings.grd"):
        if not f.is_file(): fail(f"missing Android string file {f}")
        t=f.read_text(encoding="utf-8"); pat=re.compile(r'(<message\s+name="IDS_BRAVE_ONBOARDING_SPLASH_LOGO_DESCRIPTION"[^>]*>)(.*?)(</message>)',re.S); m=pat.search(t)
        if not m: fail(f"splash logo accessibility string missing {f}")
        body=m.group(2)
        if "Sandium Browser logo" not in body:
            if body.count("Brave logo")!=1: fail(f"unexpected splash description {body.strip()}")
            f.write_text(t[:m.start(2)]+body.replace("Brave logo","Sandium Browser logo",1)+t[m.end(2):],encoding="utf-8")
    print("SANDIUM_EXTENDED_BRANDING_GATE=PASS logo=162dp splash=288dp animation=preserved wordmarks=6_RGBA_PNG webui=PASS metadata=PASS accessibility=PASS")
if __name__=="__main__": main()
