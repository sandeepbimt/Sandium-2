#!/usr/bin/env python3
import importlib.util,subprocess,tempfile,json,argparse
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('apply_news',HERE/'apply.py'); mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);source=parser.parse_args().source
manifest=json.loads((HERE/'manifest.json').read_text())
with tempfile.TemporaryDirectory(prefix='news-removal-') as d:
    core=Path(d)
    for name in manifest['files']:
        target=core/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(subprocess.check_output(['git','-C',str(source),'show',manifest['pin']+':'+name]))
    # Existing Sandium24-29 wallpaper guard must survive final removal overlay.
    ntp=core/'android/java/org/chromium/chrome/browser/ntp/BraveNewTabPageLayout.java'
    ntp.write_text(ntp.read_text().replace('                && mNtpImageGlobal instanceof Wallpaper\n','                && mNtpImageGlobal instanceof Wallpaper\n                && ((Wallpaper) mNtpImageGlobal).isSponsored()\n'))
    # Current UI overlay hides this exact preference before component removal.
    prefs=core/'android/java/brave-res/xml/brave_main_preferences.xml'
    op=next(o for o in mod.OPS if o['path'].endswith('/brave_main_preferences.xml'))
    prefs.write_text(prefs.read_text().replace(op['old'],op['old_variants'][0]))
    known=prefs.read_text()
    for bad in [known.replace(op['old_variants'][0],op['old_variants'][0].replace('false','true')),
                known+'\n'+op['old']]:
        prefs.write_text(bad)
        try:mod.apply(core)
        except RuntimeError:pass
        else:raise AssertionError('Unknown or ambiguous News preference was accepted')
        assert prefs.read_text()==bad
    prefs.write_text(known)
    mod.apply(core);mod.apply(core)
    assert 'BraveNewsPreferencesV2' not in prefs.read_text()
    assert 'isSponsored()' in ntp.read_text()
    for name in ['BraveNewTabPageLayout.java','BraveNtpAdapter.java']:
        text=(core/'android/java/org/chromium/chrome/browser/ntp'/name).read_text()
        for forbidden in ['BraveNewsController','FeedItemsCard','getNewContentCount','mIsDisplayNewsFeed']:
            assert forbidden not in text,(name,forbidden)
    sources=(core/'android/brave_java_sources.gni').read_text()
    assert '/brave_news/' not in sources and '/settings/BraveNews' not in sources
    config=(core/'build/android/config.gni').read_text()
    assert 'brave_news/common:mojom_java' not in config and 'BraveNewsControllerFactory.java' not in config
    assert 'mMvTilesContainerLayout' in ntp.read_text() and 'checkForBraveStats' in ntp.read_text()
    assert 'brave_news/renderer' not in (core/'renderer/sources.gni').read_text()
    assert 'RssLinkReader' not in (core/'renderer/brave_content_renderer_client.cc').read_text()
    renderer=(core/'renderer/brave_content_renderer_client.cc').read_text()
    assert '''#if BUILDFLAG(ENABLE_AI_CHAT) || BUILDFLAG(ENABLE_WEB_DISCOVERY_NATIVE)
  auto* registry = (new BraveRenderFrameObserver(render_frame))->registry();
#else
  new BraveRenderFrameObserver(render_frame);
#endif''' in renderer
    assert 'auto* rfo' not in renderer
    print('PASS pinned source, idempotence, wallpaper composition, News source/JNI exclusion, retained stats/top-sites')
