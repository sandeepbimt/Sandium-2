#!/usr/bin/env python3
"""Document-linked browser receipt of first nonempty paint, not GPU presentation."""
PATH='content/browser/web_contents/web_contents_impl.cc'
OLD='''void WebContentsImpl::OnFirstVisuallyNonEmptyPaint(PageImpl& page) {
  OPTIONAL_TRACE_EVENT1(
      "content", "WebContentsImpl::OnFirstVisuallyNonEmptyPaint", "page", page);
  if (!page.IsPrimary()) {
    return;
  }'''
NEW=OLD+'''
  // SANDIUM_DIAGNOSTIC_DOCUMENT_PAINT_V1: actual owning document, not current URL.
  if (GetContentClient()->browser()->IsSandiumNavigationDiagnosticsEnabled(this)) {
    GetContentClient()->browser()->RecordSandiumNavigationDiagnostic(
        this, 25, page.GetMainDocument().GetNavigationId(),
        base::TimeTicks::Now().since_origin().InMicroseconds(), {1., 0., 0.});
  }
'''
def transform(s):
 if NEW in s:return s
 if s.count(OLD)!=1:raise ValueError('Document paint anchor drift')
 return s.replace(OLD,NEW,1)
