Exact Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51 fixtures retrieved from official Gitiles. Manifest records SHA256.

The producer is called only within the existing accepted OnTimingUpdated tracker branch, before moving render_data to the normal upstream consumer. It does not suppress or change upstream metrics. It records primary-page, main or child frame batches correlated to the accepted primary page load tracker's actual navigation ID, not an arbitrary current URL/tab ID.

Event 27 fields: outermost_main_frame,count,total_score,non_input_score,input_or_scroll_count,first_renderer_ticks_us,last_renderer_ticks_us. source_ticks_us is BROWSER RECEIPT time. The last two values are renderer event timestamps. These batches are deltas, not cumulative/windowed CLS. Do not sum repeated first-paint observations, claim GPU presentation, identify a changed DOM element, or attribute shifts specifically to dark mode/typography from these metrics alone.

Timing is already buffered by the upstream renderer. A recording started mid-navigation may receive earlier buffered renderer events: use the event timestamp range, do not treat receipt time as the shift time. Bound/count checks and opt-in/private policy are enforced by the existing bridge; invalid/nonfinite/empty batches emit nothing. No URL/text/DOM identifiers are included.

Production restore owners:
- components/page_load_metrics/browser/metrics_web_contents_observer.cc
- components/page_load_metrics/browser/page_load_tracker.h

Neither owner has a matching +++ b/ patch target in the pinned Brave patch inventory. Both must be reset/replayed by the diagnostics recipe and composition harness. Apply after the browser-to-Java bridge; reserve Java event27 with7 fields. This module intentionally does not edit shared Java enum/recipe owned by the integrator.

Actual dark or typography renderer application time is still NOT implemented. Browser policy dispatch is not application. That requires a separate provenance-safe renderer→browser transport or a real renderer trace, with early Document/StyleEngine hooks, document/recording epoch checks and privacy tests.
