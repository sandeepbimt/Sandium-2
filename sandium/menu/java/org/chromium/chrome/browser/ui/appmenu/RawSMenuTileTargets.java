package org.chromium.chrome.browser.ui.appmenu;

import android.view.View;
import java.util.List;

/** Only actionable current tile roots; never enclosing grid, rows, icon/text descendants.
 * Consumed by the narrow native AppMenuDragHelper hook, preserving its screen hit-testing,
 * entrance gating, button-exit gating and native cancellation/dismissal lifecycle.
 */
interface RawSMenuTileTargets {
    List<View> rawSVisibleTileTargets();
}
