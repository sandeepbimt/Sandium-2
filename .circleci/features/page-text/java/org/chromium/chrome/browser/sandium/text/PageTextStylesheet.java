// Copyright 2026 Sandium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license.
package org.chromium.chrome.browser.sandium.text;

import java.util.Objects;

/** Bounded stylesheet compiler for a future document-start consumer. No JS or DOM scan.
 * No caller-controlled CSS, selector, URL, text or font-family is interpolated.
 */
public final class PageTextStylesheet {
    private PageTextStylesheet() {}

    // Conservative semantic article bodies only. Never use body/main as heuristic fallback.
    // Native consumer separately installs in HTTP frames; shadow coverage needs renderer tests.
    private static final String EXCLUDED =
            "nav,header,footer,aside,form,button,textarea,input,select,figure,table,pre,code,"
            + "[role=navigation],[role=button],[role=textbox],[role=dialog],"
            + "[contenteditable]:not([contenteditable=false]),[aria-hidden=true],"
            + ".comments,#comments";
    private static final String SELECTOR =
            ":where(article,[role=article],[itemprop=articleBody]) p"
            + ":not(:where(" + EXCLUDED + "))"
            + ":not(:where(" + EXCLUDED + ") *)";

    public static String compile(PageTextPolicy.Settings settings) {
        Objects.requireNonNull(settings);
        StringBuilder css = new StringBuilder();
        // Native Chromium text adjustment, not CSS font-size or page zoom.
        // Website default installs no scale rule, preserving author/accessibility behavior.
        if (settings.scalePercent != 100) {
            css.append("*{-webkit-text-size-adjust:").append(settings.scalePercent)
                    .append("% !important;text-size-adjust:").append(settings.scalePercent)
                    .append("% !important;}");
        }
        if (settings.enabled && settings.justify) {
            css.append(SELECTOR).append("{text-align:justify !important;}");
        }
        return css.toString();
    }
}
