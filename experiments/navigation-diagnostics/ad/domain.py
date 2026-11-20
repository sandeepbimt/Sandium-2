"""Numeric domain-throttle operations; actual nav ID and lifetime-owned epoch."""
HEADER='components/brave_shields/content/browser/domain_block_navigation_throttle.h'
SOURCE='components/brave_shields/content/browser/domain_block_navigation_throttle.cc'
def once(s,old,new):
 if new in s:return s
 if s.count(old)!=1:raise ValueError('Domain diagnostic drift: '+old[:100])
 return s.replace(old,new,1)
def header(s):
 s=once(s,'#include <memory>','#include <memory>\n#include "base/time/time.h"') if '#include <memory>' in s else once(s,'#include "base/memory/raw_ptr.h"','#include "base/time/time.h"\n#include "base/memory/raw_ptr.h"')
 return once(s,' private:\n  void OnShouldBlockDomain',''' private:
  // SANDIUM_DOMAIN_DIAGNOSTIC_V1: no retained WebContents or URL diagnostics.
  int64_t sandium_diagnostic_epoch_ = 0;
  base::TimeTicks sandium_diagnostic_started_;
  void ReportSandiumDomainDiagnostic(int phase, bool blocked, bool rewritten);
  void OnShouldBlockDomain''')
REPORT='''void DomainBlockNavigationThrottle::ReportSandiumDomainDiagnostic(
    int phase, bool blocked, bool rewritten) {
  if (sandium_diagnostic_epoch_ <= 0) return;
  auto* handle = navigation_handle();
  const auto now = base::TimeTicks::Now();
  content::ContentBrowserClient::RecordSandiumDiagnosticForEpoch(
      handle->GetWebContents(), sandium_diagnostic_epoch_, 11,
      handle->GetNavigationId(), now.since_origin().InMicroseconds(),
      {0, static_cast<double>(phase),
       static_cast<double>(blink::mojom::ResourceType::kMainFrame), -1,
       blocked ? 1.0 : 0.0, 0, rewritten ? 1.0 : 0.0,
       static_cast<double>((now - sandium_diagnostic_started_).InMicroseconds())});
}

'''
LEGACY_EPOCH = '  sandium_diagnostic_epoch_ = content::ContentBrowserClient::SandiumDiagnosticsEpoch(web_contents);'
GATED_EPOCH = '''  sandium_diagnostic_epoch_ =
      AdBlockService::IsSandiumAdDiagnosticsRecording()
          ? content::ContentBrowserClient::SandiumDiagnosticsEpoch(web_contents)
          : 0;'''
CHANGES=[
('#include "content/public/browser/browser_context.h"','#include "content/public/browser/browser_context.h"\n#include "content/public/browser/content_browser_client.h"'),
('''  content::WebContents* web_contents = handle->GetWebContents();
  // Maybe don't block''','''  content::WebContents* web_contents = handle->GetWebContents();
'''+GATED_EPOCH+'''
  if (sandium_diagnostic_epoch_ > 0) sandium_diagnostic_started_ = base::TimeTicks::Now();
  // Maybe don't block'''),
('''  if (domain_blocking_type == DomainBlockingType::kNone) {
    DomainBlockTabStorage*''','''  if (domain_blocking_type == DomainBlockingType::kNone) {
    ReportSandiumDomainDiagnostic(30, false, false);
    DomainBlockTabStorage*'''),
('''  if (tab_storage->IsProceeding()) {
    return''','''  if (tab_storage->IsProceeding()) {
    ReportSandiumDomainDiagnostic(31, false, false);
    return'''),
('''  ad_block_service_->AsyncCallAndReplyWithResult<BlockResult>(''','''  ReportSandiumDomainDiagnostic(32, false, false);
  ad_block_service_->AsyncCallAndReplyWithResult<BlockResult>('''),
('''  const GURL new_url(block_result.new_url);

  if (should_block''','''  const GURL new_url(block_result.new_url);
  ReportSandiumDomainDiagnostic(new_url.is_valid() ? 12 : (should_block ? 11 : 10),
                                should_block, new_url.is_valid());

  if (should_block'''),
('''  CancelDeferredNavigation(content::NavigationThrottle::ThrottleCheckResult(
      content::NavigationThrottle::CANCEL, net::ERR_BLOCKED_BY_CLIENT,''','''  ReportSandiumDomainDiagnostic(15, true, false);
  CancelDeferredNavigation(content::NavigationThrottle::ThrottleCheckResult(
      content::NavigationThrottle::CANCEL, net::ERR_BLOCKED_BY_CLIENT,'''),
('''          navigation_handle()->GetURL())) {
    Resume();''','''          navigation_handle()->GetURL())) {
    ReportSandiumDomainDiagnostic(16, false, false);
    Resume();'''),
('''  } else if (tab_storage) {
    tab_storage->Enable1PESForUrlIfPossible(''','''  } else if (tab_storage) {
    ReportSandiumDomainDiagnostic(17, false, false);
    tab_storage->Enable1PESForUrlIfPossible('''),
('''void DomainBlockNavigationThrottle::On1PESState(bool is_1pes_enabled) {
  if''','''void DomainBlockNavigationThrottle::On1PESState(bool is_1pes_enabled) {
  ReportSandiumDomainDiagnostic(is_1pes_enabled ? 18 : 19, false, false);
  if'''),
('''  CancelDeferredNavigation(content::NavigationThrottle::ThrottleCheckResult(
      content::NavigationThrottle::CANCEL));''','''  ReportSandiumDomainDiagnostic(20, false, true);
  CancelDeferredNavigation(content::NavigationThrottle::ThrottleCheckResult(
      content::NavigationThrottle::CANCEL));'''),
('''void DomainBlockNavigationThrottle::OnShouldBlockDomain(''',REPORT+'''void DomainBlockNavigationThrottle::OnShouldBlockDomain('''),
]
def source(s):
 s=s.replace(LEGACY_EPOCH,GATED_EPOCH,1)
 for old,new in CHANGES:s=once(s,old,new)
 return s
