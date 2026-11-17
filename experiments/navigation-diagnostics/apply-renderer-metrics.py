#!/usr/bin/env python3
"""Numeric renderer-reported layout-shift batches, not CLS or policy-apply timing."""
OBSERVER='components/page_load_metrics/browser/metrics_web_contents_observer.cc'
TRACKER='components/page_load_metrics/browser/page_load_tracker.h'
def once(s,old,new):
 if new in s:return s
 if s.count(old)!=1:raise ValueError('Renderer metrics anchor drift: '+old[:80])
 return s.replace(old,new,1)
def tracker(s):
 return once(s,'  ukm::SourceId GetPageUkmSourceId() const override;','''  // SANDIUM_RENDERER_METRICS_V1: document navigation identity, never a URL.
  int64_t GetSandiumDiagnosticNavigationId() const { return navigation_id_; }
  ukm::SourceId GetPageUkmSourceId() const override;''')
BLOCK='''    // SANDIUM_RENDERER_METRICS_V1: actual renderer deltas, browser receive time.
    // Primary-page tracker identity excludes stale/inactive document updates.
    if (render_data && !render_data->new_layout_shifts.empty() &&
        render_frame_host->GetPage().IsPrimary() &&
        tracker == primary_page_.get() &&
        content::GetContentClient()->browser()->
            IsSandiumNavigationDiagnosticsEnabled(web_contents())) {
      double count = 0, score = 0, non_input_score = 0, input_count = 0;
      int64_t first_us = 0, last_us = 0;
      for (const auto& shift : render_data->new_layout_shifts) {
        if (!shift || !std::isfinite(shift->layout_shift_score) ||
            shift->layout_shift_score < 0 ||
            shift->layout_shift_time.is_null()) continue;
        const int64_t ticks_us =
            shift->layout_shift_time.since_origin().InMicroseconds();
        if (ticks_us <= 0 ||
            !std::isfinite(score + shift->layout_shift_score)) continue;
        ++count;
        score += shift->layout_shift_score;
        if (shift->after_input_or_scroll) ++input_count;
        else non_input_score += shift->layout_shift_score;
        if (!first_us || ticks_us < first_us) first_us = ticks_us;
        if (ticks_us > last_us) last_us = ticks_us;
      }
      if (count > 0) {
        content::GetContentClient()->browser()->RecordSandiumNavigationDiagnostic(
            web_contents(), 27, tracker->GetSandiumDiagnosticNavigationId(),
            base::TimeTicks::Now().since_origin().InMicroseconds(),
            {render_frame_host->GetOutermostMainFrame() == render_frame_host
                 ? 1. : 0.,
             count, score, non_input_score, input_count,
             static_cast<double>(first_us), static_cast<double>(last_us)});
      }
    }
'''
def observer(s):
 s=once(s,'#include <algorithm>','#include <algorithm>\n#include <cmath>')
 s=once(s,'#include "content/public/browser/browser_thread.h"','#include "content/public/browser/browser_thread.h"\n#include "content/public/browser/content_browser_client.h"\n#include "content/public/common/content_client.h"')
 anchor='''  if (PageLoadTracker* tracker = GetPageLoadTrackerIfValid(render_frame_host)) {
    tracker->UpdateMetrics('''
 return once(s,anchor,anchor.replace('    tracker->UpdateMetrics(',BLOCK+'    tracker->UpdateMetrics('))
