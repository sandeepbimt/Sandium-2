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
 text=(core/'android/java/org/chromium/chrome/browser/billing/InAppPurchaseWrapper.java').read_text()
 for forbidden in ['SubscriptionProduct.VPN','SubscriptionProduct.LEO','BraveVpn','BraveLeo','getSubscriptionOfferDetails','ProductType.SUBS']:
  assert forbidden not in text,forbidden
 for required in ['if (!isOriginProduct) return;', 'BillingClient.ProductType.INAPP', 'BraveOriginSubscriptionPrefs.setOriginPurchaseToken(', 'mPurchaseProfile, purchase.getPurchaseToken()', 'queryOriginProductDetailsAsync', 'consumeExistingOriginPurchase', 'initiatePurchaseInApp']:
  assert required in text,required
 assert '"link-order"' in (core/'android/java/org/chromium/chrome/browser/billing/LinkSubscriptionUtils.java').read_text()
 # Native renderer preserves real Origin linking, but has no Leo/VPN product paths.
 native=core/'components/brave_mobile_subscription/renderer/android'
 cc=(native/'subscription_render_frame_observer.cc').read_text()
 header=(native/'subscription_render_frame_observer.h').read_text()
 gn=(native/'BUILD.gn').read_text()
 for forbidden in ('ai_chat', 'kLeo', 'kVPN', 'braveLeo', 'braveVpn', 'enable_brave_vpn'):
  assert forbidden not in cc+header+gn,forbidden
 for required in ('base::FeatureList::IsEnabled(brave_origin::features::kBraveOrigin)',
                  'origin_subscription_->GetPurchaseTokenOrderId',
                  'origin_subscription_->SetLinkStatus',
                  'skus::IsSafeOrigin(', '"braveOrigin.receipt"', '"braveOrigin.orderId"',
                  'if (!IsAllowed())', 'if (!IsValueAllowed(purchase_token))'):
  assert required in cc,required
 assert 'enum class Product { kOrigin = 2 };' in header
 assert 'mojo::Remote<brave_origin::mojom::OriginIAPSubscription>' in header
 assert '"//brave/components/brave_origin/mojom"' in gn
 # Corrupt an expected replacement; fail closed before writing any other file.
 op=next(o for o in mod.OPS if len(o['new']) > 100)
 target=core/op['path'];target.write_text(target.read_text().replace(op['new'],'SOURCE_DRIFT_SENTINEL',1))
 snapshot={p:p.read_bytes() for p in core.rglob('*') if p.is_file()}
 try:mod.apply(core)
 except RuntimeError:pass
 else:raise AssertionError('unknown source accepted')
 assert all(p.read_bytes()==data for p,data in snapshot.items())
 print('PASS pinned source, repeat apply, source drift atomic rejection, component contracts')
