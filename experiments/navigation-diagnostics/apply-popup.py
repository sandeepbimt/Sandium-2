#!/usr/bin/env python3
"""Browser-received popup attempt/outcome; no renderer-side suppression claim."""
import re
PATH='content/browser/renderer_host/render_frame_host_impl.cc'
START='''void RenderFrameHostImpl::CreateNewWindow(
    mojom::CreateNewWindowParamsPtr params,
    CreateNewWindowCallback callback) {'''
END='\nvoid RenderFrameHostImpl::SendLegacyTechEvent('
PROBE='''
  // SANDIUM_DIAGNOSTIC_POPUP_V1: opaque process-local token, no target URL.
  auto* sandium_diag_client = GetContentClient()->browser();
  const int64_t sandium_diag_epoch = sandium_diag_client->GetSandiumNavigationDiagnosticsEpoch(
      WebContents::FromRenderFrameHost(this));
  static uint64_t sandium_popup_sequence = 0;
  const double sandium_popup_token = sandium_diag_epoch ? ++sandium_popup_sequence : 0;
  const int64_t sandium_popup_nav = sandium_diag_epoch ? GetNavigationId() : 0;
  auto sandium_popup_weak = sandium_diag_epoch ? GetWeakPtr()
      : base::WeakPtr<RenderFrameHostImpl>();
  const auto sandium_popup_start = sandium_diag_epoch ? base::TimeTicks::Now() : base::TimeTicks();
  bool sandium_popup_recorded = false;
  auto sandium_record_popup = [&](double status, double reason, bool child_available) {
    if (!sandium_diag_epoch || sandium_popup_recorded || !sandium_popup_weak) return;
    sandium_popup_recorded = true;
    GetContentClient()->browser()->RecordSandiumNavigationDiagnosticForEpoch(
        WebContents::FromRenderFrameHost(sandium_popup_weak.get()), sandium_diag_epoch,
        20, sandium_popup_nav, base::TimeTicks::Now().since_origin().InMicroseconds(),
        {sandium_popup_token, status, reason, child_available ? 1. : 0.,
         static_cast<double>((base::TimeTicks::Now() - sandium_popup_start).InMicroseconds()), 0.});
  };
  std::optional<base::ScopedClosureRunner> sandium_popup_end;
  if (sandium_diag_epoch) {
    sandium_diag_client->RecordSandiumNavigationDiagnosticForEpoch(
        WebContents::FromRenderFrameHost(this), sandium_diag_epoch, 9, sandium_popup_nav,
        sandium_popup_start.since_origin().InMicroseconds(),
        {sandium_popup_token, params->started_with_transient_activation ? 1. : 0.,
         static_cast<double>(params->disposition)});
    // Chromium BindOnce requires a stateless functor. The scoped runner is
    // destroyed before the earlier-declared local recorder and its references.
    sandium_popup_end.emplace(base::BindOnce(
        [](decltype(sandium_record_popup)* record) { (*record)(-1., 1., false); },
        base::Unretained(&sandium_record_popup)));
  }
'''
def transform(s):
 if 'SANDIUM_DIAGNOSTIC_POPUP_V1' in s:return s
 if s.count(START)!=1 or s.count(END)!=1:raise ValueError('Popup function anchors drift')
 begin=s.index(START);end=s.index(END,begin);part=s[begin:end]
 if part.count('std::move(callback).Run(mojom::CreateNewWindowStatus::')!=6:raise ValueError('Popup callback inventory drift')
 part=part.replace('  CHECK_CURRENTLY_ON(BrowserThread::UI);','  CHECK_CURRENTLY_ON(BrowserThread::UI);'+PROBE,1)
 part=re.sub(r'(?m)^(\s*)std::move\(callback\).Run\(mojom::CreateNewWindowStatus::(\w+),',lambda m:m[1]+'sandium_record_popup(static_cast<double>(mojom::CreateNewWindowStatus::'+m[2]+'), 0., '+('shown_contents != nullptr' if m[2]=='kSuccess' else 'false')+');\n'+m[0],part)
 return s[:begin]+part+s[end:]
