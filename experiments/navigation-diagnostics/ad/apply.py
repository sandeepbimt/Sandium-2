#!/usr/bin/env python3
"""Held, numeric UI request-result instrumentation. No engine behavior changes."""
from pathlib import Path
PATH='browser/net/brave_ad_block_tp_network_delegate_helper.cc'
HELPERS='''// SANDIUM_AD_DIAGNOSTICS_V1: anonymous numeric state only, never request URLs/rules.
struct SandiumAdDiagnostic {
  int64_t epoch = 0;
  int64_t request = 0;
  int resource_type = 0;
  base::TimeTicks started;
  content::GlobalRenderFrameHostToken frame_token;
  bool redirect_present = false;
  bool rewrite_present = false;
  bool cname_query = false;
};

int64_t g_sandium_ad_budget_epoch = 0;
int64_t g_sandium_ad_next_request = 0;
std::array<int64_t, 4> g_sandium_ad_last_load_sequence{{-1, -1, -1, -1}};

void ReportSandiumAdLoadSnapshot(content::WebContents* contents, int64_t epoch) {
  auto* service = g_brave_browser_process->ad_block_service();
  if (!service) return;
  const auto snapshot = service->GetSandiumDiagnosticLoadSnapshot();
  for (size_t i = 0; i < snapshot.size(); ++i) {
    const auto& row = snapshot[i];
    if (g_sandium_ad_last_load_sequence[i] == row[3]) continue;
    const bool baseline = g_sandium_ad_last_load_sequence[i] < 0;
    g_sandium_ad_last_load_sequence[i] = row[3];
    content::ContentBrowserClient::RecordSandiumDiagnosticForEpoch(
        contents, epoch, 10, 0, base::TimeTicks::Now().since_origin().InMicroseconds(),
        {static_cast<double>(row[0]), static_cast<double>(row[1]),
         static_cast<double>(row[2]), static_cast<double>(row[3]), -1,
         baseline ? 1.0 : 0.0});
  }
}

template <template <typename> class T>
SandiumAdDiagnostic BeginSandiumAdDiagnostic(T<BraveRequestInfo> ctx) {
  SandiumAdDiagnostic diagnostic;
  if (!content::BrowserThread::CurrentlyOn(content::BrowserThread::UI) || !ctx) return diagnostic;
  auto* frame = content::RenderFrameHost::FromFrameToken(ctx->render_frame_token());
  auto* contents = content::WebContents::FromRenderFrameHost(frame);
  const int64_t epoch = content::ContentBrowserClient::SandiumDiagnosticsEpoch(contents);
  if (epoch <= 0) return diagnostic;
  if (g_sandium_ad_budget_epoch != epoch) {
    g_sandium_ad_budget_epoch = epoch; g_sandium_ad_next_request = 0;
    g_sandium_ad_last_load_sequence.fill(-1);
  }
  ReportSandiumAdLoadSnapshot(contents, epoch);
  if (++g_sandium_ad_next_request > 512) {
    // One aggregate count per omitted request; recorder does not append a row.
    content::ContentBrowserClient::RecordSandiumDiagnosticForEpoch(
        contents, epoch, 24, 0, base::TimeTicks::Now().since_origin().InMicroseconds(), {1});
    return diagnostic;
  }
  diagnostic.epoch = epoch;
  diagnostic.request = g_sandium_ad_next_request;
  diagnostic.resource_type = static_cast<int>(ctx->resource_type());
  diagnostic.started = base::TimeTicks::Now();
  diagnostic.frame_token = ctx->render_frame_token();
  return diagnostic;
}

void ReportSandiumAdDiagnostic(const SandiumAdDiagnostic& diagnostic, int phase,
                               int blocked_by, const EngineFlags& flags) {
  if (!content::BrowserThread::CurrentlyOn(content::BrowserThread::UI) || diagnostic.epoch <= 0) return;
  const auto now = base::TimeTicks::Now();
  auto* frame = content::RenderFrameHost::FromFrameToken(diagnostic.frame_token);
  auto* contents = content::WebContents::FromRenderFrameHost(frame);
  if (content::ContentBrowserClient::SandiumDiagnosticsEpoch(contents)
      != diagnostic.epoch) return;
  ReportSandiumAdLoadSnapshot(contents, diagnostic.epoch);
  const int bits = (flags.did_match_rule ? 1 : 0) |
                   (flags.did_match_exception ? 2 : 0) |
                   (flags.did_match_important ? 4 : 0);
  content::ContentBrowserClient::RecordSandiumDiagnosticForEpoch(
      contents, diagnostic.epoch, 11, 0, now.since_origin().InMicroseconds(),
      {static_cast<double>(diagnostic.request), static_cast<double>(phase),
       static_cast<double>(diagnostic.resource_type), static_cast<double>(blocked_by),
       static_cast<double>(bits), diagnostic.redirect_present ? 1.0 : 0.0,
       diagnostic.rewrite_present ? 1.0 : 0.0,
       static_cast<double>((now - diagnostic.started).InMicroseconds())});
}

'''
CHANGES=[
('#include <memory>', '#include <array>\n#include <memory>', 1),
('''  if (!ctx) {
    next_callback.Run();
    return;
  }
  ctx->set_blocked_by''','''  if (!ctx) {
    ReportSandiumAdDiagnostic(diagnostic, 5, -1, result.engine_flags);
    next_callback.Run();
    return;
  }
  ctx->set_blocked_by''',1),
('''  if (!ctx || !ctx->request_initiator()) {
    next_callback.Run();
    return;
  }''','''  if (!ctx || !ctx->request_initiator()) {
    ReportSandiumAdDiagnostic(diagnostic, 5, -1, previous_result);
    next_callback.Run();
    return;
  }''',1),

('''                                   ctx->devtools_request_id()};
    auto* ad_block_service''','''                                   ctx->devtools_request_id()};
    diagnostic.cname_query = true;
    auto* ad_block_service''',1),

('#include "content/public/browser/browser_context.h"','#include "content/public/browser/browser_context.h"\n#include "content/public/browser/content_browser_client.h"\n#include "base/time/time.h"',1),
('struct ShouldBlockRequestParams {',HELPERS+'struct ShouldBlockRequestParams {',1),
('''                    EngineFlags previous_result,
                    std::optional<std::string> cname)''','''                    EngineFlags previous_result,
                    SandiumAdDiagnostic diagnostic,
                    std::optional<std::string> cname)''',2),
('''      EngineFlags previous_result) {
    DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
    cb_ = base::BindOnce(&UseCnameResult<T>, std::move(next_callback), ctx,
                         previous_result);''','''      EngineFlags previous_result, SandiumAdDiagnostic diagnostic) {
    DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
    cb_ = base::BindOnce(&UseCnameResult<T>, std::move(next_callback), ctx,
                         previous_result, diagnostic);''',1),
('''                                T<BraveRequestInfo> ctx,
                                ShouldBlockRequestResult result) {''','''                                T<BraveRequestInfo> ctx,
                                SandiumAdDiagnostic diagnostic,
                                ShouldBlockRequestResult result) {''',1),
('''  ctx->set_blocked_by(result.blocked_by);
  ctx->set_mock_data_url''','''  diagnostic.redirect_present |= !result.mock_data_url.empty();
  diagnostic.rewrite_present |= !result.new_url_spec.empty();
  ReportSandiumAdDiagnostic(diagnostic,
      then_check_uncloaked && result.blocked_by != kAdBlocked ? 0 :
          (diagnostic.cname_query ? 2 : 1),
      static_cast<int>(result.blocked_by), result.engine_flags);
  ctx->set_blocked_by(result.blocked_by);
  ctx->set_mock_data_url''',1),
('''                                         result.engine_flags);''','''                                         result.engine_flags, diagnostic);''',1),
('''        base::BindOnce(&OnShouldBlockRequestResult<T>, false, next_callback,
                       ctx));
  } else {
    next_callback.Run();
  }
}''','''        base::BindOnce(&OnShouldBlockRequestResult<T>, false, next_callback,
                       ctx, diagnostic));
  } else {
    ReportSandiumAdDiagnostic(diagnostic, 3, static_cast<int>(ctx->blocked_by()), previous_result);
    next_callback.Run();
  }
}''',1),
('''                     next_callback, ctx));
}

template <template <typename> class T>
int OnBeforeURLRequest_AdBlockTPPreWork''','''                     next_callback, ctx, BeginSandiumAdDiagnostic(ctx)));
}

template <template <typename> class T>
int OnBeforeURLRequest_AdBlockTPPreWork''',1),
]
for condition, phase in [
    ('ctx->resource_type() == BraveRequestInfo::kInvalidResourceType) {', 6),
    ('!ctx->request_url().SchemeIsWSOrWSS()) {', 7),
    ('::brave_shields::features::kBraveExtensionNetworkBlocking)) {', 8),
]:
 old = '      ' + condition + '\n    return net::OK;'
 # Scheme indentation is six spaces in the actual pinned file, as are both others.
 new = '      ' + condition + '\n    ReportSandiumAdDiagnostic(BeginSandiumAdDiagnostic(ctx), '+str(phase)+', static_cast<int>(kNotBlocked), {});\n    return net::OK;'
 CHANGES.append((old,new,2 if phase == 7 else 1))
# The main-frame skip shares the scheme suffix; its complete condition is distinct.
CHANGES.append(('''  if (ctx->resource_type() == blink::mojom::ResourceType::kMainFrame &&
      !ctx->request_url().SchemeIsWSOrWSS()) {
    ReportSandiumAdDiagnostic(BeginSandiumAdDiagnostic(ctx), 7, static_cast<int>(kNotBlocked), {});''','''  if (ctx->resource_type() == blink::mojom::ResourceType::kMainFrame &&
      !ctx->request_url().SchemeIsWSOrWSS()) {
    ReportSandiumAdDiagnostic(BeginSandiumAdDiagnostic(ctx), 9, static_cast<int>(kNotBlocked), {});''',1))
def transform(s):
 if 'SANDIUM_AD_DIAGNOSTICS_V1' in s:
  for old,new,count in reversed(CHANGES):
   if s.count(new)!=count:raise ValueError('Existing diagnostic drift: '+new[:90])
   s=s.replace(new,old)
 for old,new,count in CHANGES:
  if s.count(new)==count:continue
  if s.count(old)!=count:raise ValueError('Ad diagnostic anchor drift: '+old[:110])
  s=s.replace(old,new)
 return s
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('core',type=Path);p.add_argument('--apply',action='store_true');a=p.parse_args();
 import importlib.util
 spec=importlib.util.spec_from_file_location('load_snapshot',Path(__file__).with_name('load_snapshot.py'));load=importlib.util.module_from_spec(spec);spec.loader.exec_module(load)
 spec=importlib.util.spec_from_file_location('domain',Path(__file__).with_name('domain.py'));domain=importlib.util.module_from_spec(spec);spec.loader.exec_module(domain)
 spec=importlib.util.spec_from_file_location('baseline',Path(__file__).with_name('baseline.py'));baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
 output={a.core/PATH:transform((a.core/PATH).read_text()),a.core/load.HEADER:load.header((a.core/load.HEADER).read_text()),a.core/load.SOURCE:load.source((a.core/load.SOURCE).read_text()),a.core/domain.HEADER:domain.header((a.core/domain.HEADER).read_text()),a.core/domain.SOURCE:domain.source((a.core/domain.SOURCE).read_text()),a.core/baseline.JAVA:baseline.java((a.core/baseline.JAVA).read_text()),a.core/baseline.CPP:baseline.cpp((a.core/baseline.CPP).read_text())}
 if a.apply:
  for target,out in output.items():target.write_text(out)
 print('AD diagnostic source plan valid; transport/schema prerequisites not activated')
