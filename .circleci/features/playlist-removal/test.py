#!/usr/bin/env python3
"""Pinned fixture, replay, atomic drift rejection; requires a local Brave git checkout."""
import argparse, importlib.util, json, subprocess, tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('overlay',HERE/'apply.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);args=p.parse_args()
m=json.loads((HERE/'manifest.json').read_text())
with tempfile.TemporaryDirectory() as d:
 core=Path(d)
 for path in m['touched_files']:
  target=core/path;target.parent.mkdir(parents=True,exist_ok=True)
  target.write_bytes(subprocess.check_output(['git','-C',str(args.source),'show',m['pin']+':'+path]))
 mod.apply(core);snapshot={p:p.read_bytes() for p in core.rglob('*') if p.is_file()};mod.apply(core)
 assert all(p.read_bytes()==data for p,data in snapshot.items())
 sources=(core/'android/brave_java_sources.gni').read_text()
 assert '/playlist/' not in sources and 'HlsService.java' not in sources
 config=(core/'build/android/config.gni').read_text()
 assert 'brave_app_playlist_deps' not in config and 'PlaylistServiceFactory.java' not in config
 manifest=(core/'android/java/AndroidManifest.xml').read_text()
 assert '.playlist.' not in manifest
 toolbar=(core/'android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java').read_text()
 assert 'PlaylistService' not in toolbar and 'BraveRewardsNativeWorker' in toolbar
 assert 'assert(!is_android' not in (core/'components/playlist/core/common/buildflags/buildflags.gni').read_text()
 # Regression: the subsequent VPN transform removes the sole residual link branch.
 activity=core/'android/java/org/chromium/chrome/browser/app/BraveActivity.java'
 source=activity.read_text()
 start=source.index('            if (lastPathSegment != null')
 end=source.index('\n            }',start)+len('\n            }')
 known=source[start:end]
 assert 'DEEPLINK_ANDROID_VPN' in known and 'DEEPLINK_ANDROID_PLAYLIST' not in known
 activity.write_text(source[:start]+source[end:])
 # Also remove the independent deferred VPN block as the VPN overlay does.
 # Retirement predicate only examines the URL-intent block, while checking all VPN symbols absent.
 source=activity.read_text().replace('BraveConstants.DEEPLINK_ANDROID_VPN','REMOVED_VPN_CONSTANT')
 activity.write_text(source)
 mod.apply(core)
 assert not mod.retired_by_vpn(next(o for o in mod.OPS if o['anchor']=='BraveConstants.DEEPLINK_ANDROID_PLAYLIST'),source.replace('String lastPathSegment = appLinkData.getLastPathSegment();','unexpected();'))
 # Corrupt an expected replacement; fail closed before writing any other file.
 op=next(o for o in mod.OPS if len(o['new']) > 30 and o['new'] in (core/o['path']).read_text())
 target=core/op['path'];target.write_text(target.read_text().replace(op['new'],'SOURCE_DRIFT_SENTINEL',1))
 snapshot={p:p.read_bytes() for p in core.rglob('*') if p.is_file()}
 try:mod.apply(core)
 except RuntimeError:pass
 else:raise AssertionError('unknown source accepted')
 assert all(p.read_bytes()==data for p,data in snapshot.items())
 print('PASS pinned source, repeat apply, source drift atomic rejection, component contracts')
